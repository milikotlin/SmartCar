"""Visual and functional check of the dashboard in a REAL browser (headless Chrome driven through the DevTools protocol), at desktop and phone size.

For each scenario it opens the dashboard, searches a plate, makes DOM assertions (what must and must not be on the page), checks horizontal overflow and
saves PNG screenshots to docs/screenshots/. It needs the stack running (docker compose up) and `websocket-client`.

Usage:  python scripts/visual_check.py
"""
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "docs" / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)
CHROME = next(p for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe") if os.path.exists(p))
URL = "http://localhost:3000"
PORT = 9333
results: list[tuple[str, bool, str]] = []


def record(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""), flush=True)


class Page:
    def __init__(self):
        self.profile = tempfile.mkdtemp(prefix="smartcar_chrome_")
        self.proc = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={PORT}", f"--user-data-dir={self.profile}", "--no-first-run", "--disable-gpu", "--hide-scrollbars", "about:blank"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=2))
                page = next(t for t in tabs if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.5)
        self.ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=60, suppress_origin=True)
        self.n = 0
        self.send("Page.enable")
        self.send("Runtime.enable")

    def send(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def js(self, expr):
        r = self.send("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in r:
            raise RuntimeError(r["exceptionDetails"].get("exception", {}).get("description", "js error"))
        return r["result"].get("value")

    def device(self, width, height, mobile):
        self.send("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=1.5 if mobile else 1, mobile=mobile)

    def scheme(self, dark):
        self.send("Emulation.setEmulatedMedia", media="screen", features=[{"name": "prefers-color-scheme", "value": "dark" if dark else "light"}])

    def open(self):
        self.send("Page.navigate", url=URL)
        self.js("new Promise(r => setTimeout(r, 2500))")

    def search(self, plate, wait=9):
        self.js("""(async () => {
          const input = document.querySelector('input[aria-label^="License plate"]');
          Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, '%s');
          input.dispatchEvent(new Event('input', {bubbles: true}));
          document.querySelector('form[role="search"]').requestSubmit();
        })()""" % plate)
        self.js("new Promise(r => setTimeout(r, %d))" % (wait * 1000))

    def text(self):
        return self.js("document.body.innerText")

    def shot(self, name, selector=None, viewport=False):
        if viewport:
            self.js("scrollTo(0, 0)")
            data = self.send("Page.captureScreenshot", format="png")["data"]
            path = SHOTS / f"{name}.png"
            path.write_bytes(base64.b64decode(data))
            return path
        if selector:
            box = self.js("(() => { const e = document.querySelector(%s); if (!e) return null; const r = e.getBoundingClientRect(); return {x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height}; })()" % json.dumps(selector))
            if not box:
                return None
            clip = {"x": max(box["x"] - 8, 0), "y": max(box["y"] - 8, 0), "width": box["w"] + 16, "height": box["h"] + 16, "scale": 1}
        else:
            m = self.send("Page.getLayoutMetrics")
            size = m["cssContentSize"]
            clip = {"x": 0, "y": 0, "width": size["width"], "height": min(size["height"], 6000), "scale": 1}
        data = self.send("Page.captureScreenshot", format="png", captureBeyondViewport=True, clip=clip)["data"]
        path = SHOTS / f"{name}.png"
        path.write_bytes(base64.b64decode(data))
        return path

    def overflow(self):
        return self.js("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1")

    def close(self):
        try:
            self.ws.close()
        finally:
            self.proc.terminate()


FORBIDDEN = ["times the average", "x the average", "probability of failure", "chance of failure", "% chance", "will fail", "failure risk"]


def common_checks(page, label):
    t = page.text().lower()
    for f in FORBIDDEN:
        record(f"{label}: does not contain '{f}'", f not in t)
    record(f"{label}: no horizontal overflow", not page.overflow())


FLUFF = ["not validated", "synthetic", "typical values", "how to read this", "what this level is worth", "not a probability"]


def no_fluff(page, label):
    """The defence UI shows labels and badges, not caveat paragraphs (they live in docs/ and the ML drawer's numbers)."""
    t = page.js("[...document.querySelectorAll('main article, main section:not([data-testid=\"ml-metrics\"] *)')].filter(e => !e.closest('[data-testid=\"ml-metrics\"]')).map(e => e.innerText).join(' ')").lower()
    for f in FLUFF:
        record(f"{label}: no caveat prose '{f}'", f not in t)


def click(page, selector):
    page.js("document.querySelector(%s).click()" % json.dumps(selector))


def wait(page, ms):
    page.js("new Promise(r => setTimeout(r, %d))" % ms)


def main():
    page = Page()
    try:
        # ---- presentation screen (1920 x 1080): the two-stage pipeline is visible without scrolling
        page.device(1920, 1080, False)
        page.scheme(True)
        page.open()
        wait(page, 4000)                                   # let React hydrate before the first click
        click(page, "button[data-demo-plate='8878631']")
        wait(page, 9000)
        fold = page.js("""(() => { const vis = s => { const e = document.querySelector(s); return e ? e.getBoundingClientRect().bottom <= innerHeight : false; };
            return {m1: vis('[data-testid="ai-estimate"] p'), m2: vis('[data-testid="failure-risk"]'), uk: vis('[data-testid^="risk-"]')}; })()""")
        record("1080p: Model 1 KPI, Model 2 banner and subsystem gauges above the fold", all(fold.values()), str(fold))
        record("1080p: demo pill loaded the vehicle", "Nissan MICRA" in page.text())
        record("1080p: no horizontal overflow", not page.overflow())
        page.shot("presentation_1080p_dark", viewport=True)
        page.scheme(False)
        page.shot("presentation_1080p_light", viewport=True)

        for mode, (w, h, mobile) in (("desktop", (1280, 900, False)), ("mobile", (390, 844, True))):
            page.device(w, h, mobile)
            page.scheme(False)
            tag = lambda s: f"{mode}/{s}"

            # ---- 0. empty state
            page.open()
            t = page.text()
            record(tag("empty state: pipeline steps and demo pills"), "Look up a vehicle" in t and "Model 1" in t and "Model 2" in t and page.js("document.querySelectorAll('[data-demo-plate]').length") >= 4)
            page.shot(f"{mode}_00_empty")

            # ---- 1. covered vehicle, no records (Toyota Auris 2015)
            page.search("4908732")
            t = page.text()
            record(tag("vehicle header: key-value grid"), all(k in t.upper() for k in ("YEAR", "FUEL", "OWNERSHIP", "COLOR", "LAST TEST", "LICENSE VALID")) and "Toyota" in t and "White (ivory)" in t)
            record(tag("Model 1: KPI with XGBoost badge and 80% interval"), "XGBoost Regressor" in t and "80% Confidence Interval" in t and page.js("!!document.querySelector('[data-testid=\"ai-estimate\"]')"))
            page.js("document.querySelector('[data-testid=\"model1-inputs\"]').open = true")
            mi = page.js("document.querySelector('[data-testid=\"model1-inputs\"]').innerText")
            record(tag("Model 1: inputs & breakdown (official engine CC, transmission, pre-calibration)"), "Engine CC" in mi and "1,798 cc" in mi and "Automatic" in mi and "Pre-calibration output" in mi, mi[:160])
            page.shot(f"{mode}_01d_model1_inputs", "[data-testid='mileage-section']")
            fr = page.js("document.querySelector('[data-testid=\"failure-risk\"]').innerText")
            record(tag("Model 2: risk banner with level, ICE branch and driver tags"), any(f"{l} RISK" in fr.upper() for l in ("LOW", "MODERATE", "HIGH")) and "ICE Engine Pipeline" in fr
                   and "Days since service" in fr and "Brand index" in fr and "Age" in fr)
            record(tag("Model 2: no percentage shown"), "%" not in fr)
            page.shot(f"{mode}_01c_failure_risk", "[data-testid='failure-risk']")
            record(tag("comparison: three subsystem gauges with level and percentile"), page.js("document.querySelectorAll('[data-testid^=\"risk-\"]').length") == 3 and t.count("percentile") >= 3 and "Subsystem Risk" in t)
            geo = page.js("""[...document.querySelectorAll('[data-testid^="risk-"]')].map(c => { const bar = c.querySelector('[role="img"]'); const segs = [...bar.querySelectorAll('.flex.h-3 > div')]; const bw = bar.getBoundingClientRect().width; const mk = bar.querySelector('[aria-hidden="true"]').getBoundingClientRect(); return {w: segs.map(s => Math.round(s.getBoundingClientRect().width / bw * 100)), m: Math.round((mk.left + mk.width / 2 - bar.getBoundingClientRect().left) / bw * 100)}; })""")
            record(tag("comparison: bar segments 36/33/31 and the marker is inside the bar"), all(g["w"] == [36, 33, 31] and 0 <= g["m"] <= 100 for g in geo), str(geo))
            record(tag("maintenance: interval and status only"), "Recommended Maintenance" in t and "Every 12m / 15,000 km" in t and "NO RECORD" in t.upper() and "Generic service intervals" not in t)
            record(tag("recalls: crisp status"), "Open Recalls" in t and ("No open recalls" in t or "OPEN RECALL" in t.upper()))
            record(tag("service log: large actions and Save & Recalculate"), "Add Maintenance Record" in t and "Add Inspection Result" in t and "Save & Recalculate Risk" in t and "No service records" in t)
            no_fluff(page, tag("covered"))
            common_checks(page, tag("covered/no records"))
            page.shot(f"{mode}_01_covered_full")
            page.js("document.querySelector('[data-testid=\"ml-metrics\"]').open = true")
            dm = page.js("document.querySelector('[data-testid=\"ml-metrics\"]').innerText")
            record(tag("ML drawer: ROC-AUC benchmarks, feature vector and defect rates"), "benchmarks" in dm.lower() and "Previous Model 2" in dm and "real UK inspections" in dm and "Age only (baseline)" in dm
                   and "feature vector" in dm.lower() and "brand_reliability_index" in dm and "Not known:" in dm and "defect rate by level" in dm.lower(), dm[:200])
            page.shot(f"{mode}_02_ml_drawer", "[data-testid='ml-metrics']")

            # ---- 2. covered, with maintenance records and the last inspection result (seeded demo vehicle)
            page.search("6224652")
            t = page.text()
            record(tag("records: service-record KPI and AI estimate kept"), "Service record" in t and "194,227 km" in t and "AI estimate" in t)
            record(tag("records: DEMO rows, inspection tag and UK-model tag"), "DEMO" in t and "Oil and filter change" in t and "Inspection " in t and "Last inspection → UK model" in t)
            record(tag("records: brake rule flags a missing service"), "NO RECORD · OVERDUE" in t.upper())
            record(tag("records: comparison uses history"), "+ Inspection + odometer" in t or "+ Last inspection" in t)
            common_checks(page, tag("covered/with records"))
            page.shot(f"{mode}_03_records_full")

            # ---- 2b. writing records needs the workshop key
            fill = """(async (key) => { const set = (el, v) => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v); el.dispatchEvent(new Event('input', {bubbles: true})); };
              const form = [...document.querySelectorAll('form')].find(f => f.querySelector('input[name=description]'));
              set(document.querySelector('input[aria-label="Workshop key"]'), key);
              set(form.querySelector('input[name=date]'), '2026-01-15'); set(form.querySelector('input[name=km]'), '61000'); set(form.querySelector('input[name=description]'), 'visual check, must not be stored');
              form.requestSubmit(); await new Promise(r => setTimeout(r, 1500)); return document.querySelector('[data-testid="service-log"] [role=status]') ? document.querySelector('[data-testid="service-log"] [role=status]').innerText : ''; })"""
            msg = page.js(fill + "('')")
            record(tag("records form: refuses without a workshop key"), "Enter the workshop key first" in msg, msg)
            msg = page.js(fill + "('definitely-wrong-key')")
            record(tag("records form: a wrong key is rejected by the server"), "invalid workshop key" in msg.lower(), msg)
            record(tag("records form: nothing was stored"), "must not be stored" not in page.text())
            page.js("(() => { const i = document.querySelector('input[aria-label=\"Workshop key\"]'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(i, ''); i.dispatchEvent(new Event('input', {bubbles: true})); })()")
            page.shot(f"{mode}_03b_service_log", "[data-testid='service-log']")

            # ---- 3. chat on that vehicle (no OpenAI key configured in the stack)
            page.js("document.querySelector('button[aria-label^=\"Open the AI\"]').click()")
            wait(page, 600)
            page.js("""(async () => { const i = document.querySelector('input[aria-label="Describe a symptom"]');
              Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(i, 'Hearing a squeaking noise when braking');
              i.dispatchEvent(new Event('input', {bubbles: true})); i.closest('form').requestSubmit(); })()""")
            wait(page, 5000)
            dlg = page.js("document.querySelector('[role=dialog]') ? document.querySelector('[role=dialog]').innerText : ''")
            record(tag("chat: answers and says it is rule-based when the model is unavailable"), "Rule-based answer" in dlg and "not a diagnosis" in dlg)
            record(tag("chat: fits the screen"), not page.overflow())
            page.shot(f"{mode}_04_chat", viewport=True)
            page.js("document.querySelector('button[aria-label^=\"Close the AI\"]').click()")

            # ---- 2c. mileage selection: segmented toggle
            page.search("4908732")
            fill_km = lambda value: page.js("""(() => { const i = document.querySelector('#known-mileage');
              Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(i, %s); i.dispatchEvent(new Event('input', {bubbles: true})); })()""" % json.dumps(value))
            submit = lambda: page.js("document.querySelector('[data-testid=\"mileage-section\"] form').requestSubmit()")
            section = lambda: page.js("document.querySelector('[data-testid=\"mileage-section\"]').innerText")
            record(tag("mileage: AI estimate selected first, large segmented toggle"), page.js("document.querySelector('button[data-mode=\"estimate\"]').getAttribute('aria-checked')") == "true"
                   and page.js("document.querySelector('button[data-mode=\"estimate\"]').getBoundingClientRect().height") >= 48)
            click(page, "button[data-mode='reported']")
            wait(page, 300)
            t = section()
            record(tag("mileage: known-mileage field and button, no number yet"), "Use Mileage" in t and "No mileage entered" in t and page.js("!!document.querySelector('#known-mileage')"))
            for value, expected in (("", "Enter your current mileage in kilometres."), ("-5", "cannot be negative"), ("abc", "digits only"), ("12.5", "digits only"), ("0", "at least 1 km"), ("5000000", "higher than 1,000,000 km")):
                fill_km(value)
                submit()
                wait(page, 200)
                err = page.js("(document.querySelector('#mileage-error') || {}).innerText || ''")
                record(tag(f"mileage: invalid input {value!r} refused"), expected in err and "User-reported" not in section(), err)
            fill_km("123456")
            submit()
            wait(page, 2500)
            t = section()
            record(tag("mileage: valid value shown as user-reported, used by both models"), "123,456 km" in t and "User-reported" in t and "Not verified · not saved" in t and "Model 2 input ✓" in t and "UK model input ✓" in t)
            page.shot(f"{mode}_05e_mileage_user_reported", "[data-testid='mileage-section']")
            fill_km("900000")
            submit()
            wait(page, 2500)
            t = section()
            record(tag("mileage: implausible value used by neither model"), "900,000 km" in t and "Model 2 input ✗" in t and "UK model input ✗" in t)
            click(page, "button[data-mode='estimate']")
            wait(page, 2500)
            full = page.text()
            record(tag("mileage: back to the estimate leaves no typed value on screen"), "XGBoost Regressor" in full and "User-reported" not in full and "900,000" not in full)
            page.send("Network.enable")
            page.send("Network.emulateNetworkConditions", offline=False, latency=1500, downloadThroughput=-1, uploadThroughput=-1)
            click(page, "button[data-mode='reported']")
            fill_km("111111")
            submit()
            wait(page, 400)
            during = page.js("!!document.querySelector('[data-testid=\"mileage-updating\"]')")
            skeleton = page.js("document.querySelectorAll('[data-testid^=\"risk-\"]').length === 0")
            record(tag("mileage: while loading the screen says so and the old risk is not left as current"), during is True and skeleton is True)
            click(page, "button[data-mode='estimate']")
            wait(page, 6000)
            page.send("Network.emulateNetworkConditions", offline=False, latency=0, downloadThroughput=-1, uploadThroughput=-1)
            wait(page, 500)
            full = page.text()
            record(tag("mileage: switching back during a slow request ends on the estimate"), "XGBoost Regressor" in full and "User-reported" not in full and "111,111" not in full and "Updating…" not in full)
            record(tag("mileage: gauges back after the slow switch"), page.js("document.querySelectorAll('[data-testid^=\"risk-\"]').length") == 3)
            common_checks(page, tag("mileage selection"))

            # ---- 3b. Model 1 with too little training data: hybrid aged 9
            page.search("4850581")
            t = page.text()
            record(tag("hybrid aged 9: low-reliability badge with a short reason"), page.js("!!document.querySelector('[data-testid=\"low-reliability\"]')") and "LOW RELIABILITY" in t.upper() and "Official average shown" in t)
            api = page.js("fetch('http://localhost:8000/api/v1/predict/4850581').then(r => r.json()).then(b => b.mileage)")
            record(tag("hybrid aged 9: no exaggerated yearly mileage"), f"{api['estimated_km']:,} km" in t and api["estimated_annual_km"] < 25_000, str(api["estimated_annual_km"]))
            record(tag("hybrid aged 9: Model 2 uses the EV / hybrid branch"), "EV / Hybrid Branch" in t)
            page.shot(f"{mode}_04b_low_reliability", "[data-testid='mileage-section']")

            # ---- 4. electric vehicle (Tesla): comparison model not covered
            page.search("88328404")
            t = page.text()
            record(tag("electric: comparison 'Not covered' with a chip, other panels kept"), "NOT COVERED" in t.upper() and "Fuel not covered" in t and "Recommended Maintenance" in t and "Open Recalls" in t and "XGBoost Regressor" in t)
            record(tag("electric: no gauges invented"), page.js("document.querySelectorAll('[data-testid^=\"risk-\"]').length") == 0)
            record(tag("electric: Model 1 low reliability (no EV data)"), "No Israeli EV statistics" in t)
            common_checks(page, tag("electric"))
            page.shot(f"{mode}_05_not_covered_electric")

            # ---- 5. new petrol car
            page.search("62886204")
            t = page.text()
            record(tag("new car: comparison not covered, 'Under 3 years'"), "NOT COVERED" in t.upper() and "Under 3 years" in t)

            # ---- 6. official recall (Toyota 2007)
            page.search("1169762")
            t = page.text()
            record(tag("recall: open recall listed"), "OPEN RECALL" in t.upper())
            page.shot(f"{mode}_07_recall", "[data-testid='recalls']")

            # ---- 7. anomaly vehicle (60,000 km, no brake service)
            page.search("19319001")
            t = page.text()
            record(tag("anomaly: brake rule flagged from the service record"), "NO RECORD · OVERDUE" in t.upper() and "60,000 km" in t and "Service record" in t)

            # ---- 8. errors
            page.search("10000001", wait=12)
            record(tag("unknown plate: clear message"), "not found" in page.text().lower())
            page.js("""(async () => { const i = document.querySelector('input[aria-label^="License plate"]');
              Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(i, '123'); i.dispatchEvent(new Event('input', {bubbles: true}));
              document.querySelector('form[role="search"]').requestSubmit(); })()""")
            wait(page, 500)
            record(tag("invalid plate: validation message"), "Enter 7 or 8 digits" in page.text())

        # ---- dark scheme once (desktop)
        page.device(1280, 900, False)
        page.scheme(True)
        page.open()
        page.search("4908732")
        page.shot("desktop_08_dark_full")
        record("dark scheme: renders without horizontal overflow", not page.overflow())
    finally:
        page.close()
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n{passed}/{len(results)} visual checks passed")
    (ROOT / "docs" / "visual_check_results.json").write_text(json.dumps([{"check": n, "passed": ok, "detail": d} for n, ok, d in results], indent=1), encoding="utf-8")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
