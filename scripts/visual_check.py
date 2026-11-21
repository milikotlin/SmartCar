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


def main():
    page = Page()
    try:
        for mode, (w, h, mobile) in (("desktop", (1280, 900, False)), ("mobile", (390, 844, True))):
            page.device(w, h, mobile)
            page.scheme(False)
            tag = lambda s: f"{mode}/{s}"

            # ---- 0. empty state
            page.open()
            t = page.text()
            record(tag("empty state explains what to do"), "Look up a vehicle" in t)
            page.shot(f"{mode}_00_empty")

            # ---- 1. covered vehicle, no records (Toyota Auris 2015)
            page.search("4908732")
            t = page.text()
            record(tag("covered/no records: vehicle card"), "Toyota" in t and "2015" in t and "Petrol" in t)
            record(tag("covered/no records: Israeli wording, official data separated from the ML estimate"), "Last annual test (date)" in t and "Last MOT" not in t and "OFFICIAL REGISTRY DATA" in t.upper()
                   and "not its result" in t and "AI-Estimated Mileage" in t and "MILEAGE" in t.upper())
            record(tag("covered/no records: no Hebrew left on the page (colour translated)"), not __import__("re").search(r"[֐-׿]", t), t[:0])
            record(tag("covered/no records: mileage is labelled as an ESTIMATE with a range"), "AI-Estimated Mileage" in t and "Indicative range (80%)" in t and "not a measurement" in t and "I know my car's mileage" in t and "I don't know my car's mileage" in t)
            record(tag("Model 2 (PDF): main risk panel with a level, the model used and no percentage"),
                   "Risk of a mechanical failure needing maintenance" in t and "MACHINE LEARNING · MODEL 2" in t.upper() and "Model used: combustion vehicles" in t
                   and any(f"{w} RISK" in t.upper() for w in ("LOW", "MODERATE", "HIGH")) and "%" not in page.js("document.querySelector('[data-testid=\"failure-risk\"] [role=\"img\"]').getAttribute('aria-label')"))
            page.js("document.querySelector('[data-testid=\"model1-inputs\"]').open = true")
            mi = page.js("document.querySelector('[data-testid=\"model1-inputs\"]').innerText")
            record(tag("Model 1: shows the inputs it used and where they came from"), "What Model 1 used" in mi and "Engine size" in mi and "1,798 cc" in mi
                   and "Automatic" in mi and "Number of owners" in mi and "before calibration" in mi, mi[:200])
            page.shot(f"{mode}_01d_model1_inputs", "[data-testid='mileage-section']")
            record(tag("Model 2 (PDF): says what the level is worth when the service log is empty"), "What this level is worth here." in t and "no maintenance record on file" in t)
            record(tag("comparison panel: labelled as the model on real inspection data"), "COMPARISON MODEL · REAL INSPECTION DATA" in t.upper())
            page.shot(f"{mode}_01c_failure_risk", "[data-testid='failure-risk']")
            record(tag("covered/no records: three risk bars with level words"), t.count("RELATIVE RISK") == 3 and "Higher than about" in t and "Compared with vehicles aged" in t)
            record(tag("covered/no records: explanation says relative, not a probability, not validated"), "relative level" in t and "not a probability" in t and "not been validated for Israeli" in t)
            record(tag("covered/no records: maintenance panel (rules, not ML)"), "Recommended maintenance" in t and "NO RECORD" in t and "Generic service intervals" in t)
            record(tag("covered/no records: recalls panel"), "Open recalls" in t and ("No open recall" in t or "Open recall" in t))
            record(tag("covered/no records: no maintenance rows"), "No maintenance records for this vehicle yet" in t)
            record(tag("covered/no records: sentences start with a capital letter"), ". vehicle is" not in t and "Vehicle is 11 years old" in t)
            heights = page.js("[...document.querySelectorAll('[data-testid^=\"risk-\"]')].map(c => Math.round(c.querySelector('[role=\"img\"]').getBoundingClientRect().top - c.getBoundingClientRect().top))")
            record(tag("covered: the three bars sit at the same height inside their cards"), len(set(heights)) == 1 or mobile, str(heights))
            page.shot(f"{mode}_01b_maintenance", "section:has(h2)")
            common_checks(page, tag("covered/no records"))
            page.shot(f"{mode}_01_covered_full")
            page.shot(f"{mode}_01_covered_risk", "article:has([data-testid^='risk-'])")
            geo = page.js("""[...document.querySelectorAll('[data-testid^="risk-"]')].map(c => { const bar = c.querySelector('[role="img"]'); const segs = [...bar.querySelectorAll('.flex.h-3 > div')]; const bw = bar.getBoundingClientRect().width; const mk = bar.querySelector('[aria-hidden="true"]').getBoundingClientRect(); return {w: segs.map(s => Math.round(s.getBoundingClientRect().width / bw * 100)), m: Math.round((mk.left + mk.width / 2 - bar.getBoundingClientRect().left) / bw * 100)}; })""")
            record(tag("covered: bar segments 36/33/31 and the marker is inside the bar"), all(g["w"] == [36, 33, 31] and 0 <= g["m"] <= 100 for g in geo), str(geo))
            page.js("document.querySelectorAll('details').forEach(d => d.open = true)")
            t2 = page.text()
            record(tag("Model 2 (PDF): comparison table with synthetic and real-data rows"), "How well each model ranks vehicles" in t2 and "real UK MOT inspections" in t2 and "Age only (baseline)" in t2)
            record(tag("covered: details show how levels were set and observed rates"), "How often a defect was found at the next inspection" in t2 and "about" in t2 and "not a forecast for this vehicle" in t2)
            page.shot(f"{mode}_02_risk_details", "article:has([data-testid^='risk-'])")

            # ---- 2. covered, with maintenance records and the last inspection result (seeded demo vehicle)
            page.search("6224652")
            t = page.text()
            record(tag("covered/with records: measured odometer shown as MEASURED and the estimate kept for comparison"), "Recorded odometer" in t and "194,227 km" in t and "AI-Estimated Mileage (for comparison)" in t)
            record(tag("covered/with records: maintenance rows and inspection result listed"), "DEMO" in t and "Oil and filter change" in t and "ANNUAL INSPECTION RESULTS ON FILE" in t and "Manual records, not official data" in t)
            record(tag("covered/with records: the model says the last inspection result is used"), "the last inspection result is used by the comparison model" in t)
            record(tag("covered/with records: brake rule flags a missing service"), "NO RECORD, OVERDUE" in t)
            common_checks(page, tag("covered/with records"))
            page.shot(f"{mode}_03_records_full")

            # ---- 2b. writing records needs the workshop key (the form must refuse without it and with a wrong one)
            fill = """(async (key) => { const set = (el, v) => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v); el.dispatchEvent(new Event('input', {bubbles: true})); };
              const form = [...document.querySelectorAll('form')].find(f => f.querySelector('input[name=description]'));
              set(document.querySelector('input[aria-label="Workshop key"]'), key);
              set(form.querySelector('input[name=date]'), '2026-01-15'); set(form.querySelector('input[name=km]'), '61000'); set(form.querySelector('input[name=description]'), 'visual check, must not be stored');
              form.requestSubmit(); await new Promise(r => setTimeout(r, 1500)); return document.querySelector('[role=status]') ? document.querySelector('[role=status]').innerText : ''; })"""
            msg = page.js(fill + "('')")
            record(tag("records form: refuses without a workshop key"), "Enter the workshop key first" in msg, msg)
            msg = page.js(fill + "('definitely-wrong-key')")
            record(tag("records form: a wrong key is rejected by the server"), "invalid workshop key" in msg.lower(), msg)
            record(tag("records form: nothing was stored"), "must not be stored" not in page.text())
            page.js("(() => { const i = document.querySelector('input[aria-label=\"Workshop key\"]'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(i, ''); i.dispatchEvent(new Event('input', {bubbles: true})); })()")
            page.shot(f"{mode}_03b_key_refused", "section:has(form)")

            # ---- 3. chat on that vehicle (no OpenAI key configured in the stack)
            page.js("document.querySelector('button[aria-label^=\"Open the AI\"]').click()")
            page.js("new Promise(r => setTimeout(r, 600))")
            page.js("""(async () => { const i = document.querySelector('input[aria-label="Describe a symptom"]');
              Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(i, 'Hearing a squeaking noise when braking');
              i.dispatchEvent(new Event('input', {bubbles: true})); i.closest('form').requestSubmit(); })()""")
            page.js("new Promise(r => setTimeout(r, 5000))")
            dlg = page.js("document.querySelector('[role=dialog]') ? document.querySelector('[role=dialog]').innerText : ''")
            record(tag("chat: answers and says it is rule-based when the model is unavailable"), "Rule-based answer" in dlg and "not a diagnosis" in dlg and "qualified mechanic" in dlg)
            record(tag("chat: fits the screen"), not page.overflow())
            page.shot(f"{mode}_04_chat", viewport=True)
            page.js("document.querySelector('button[aria-label^=\"Close the AI\"]').click()")

            # ---- 2c. mileage selection: "I know my car's mileage" (user-reported) against "I don't know" (Model 1), on a vehicle without records (4908732)
            page.search("4908732")
            js_click = lambda sel: page.js("document.querySelector(%s).click()" % json.dumps(sel))
            wait = lambda ms: page.js("new Promise(r => setTimeout(r, %d))" % ms)
            fill = lambda value: page.js("""(() => { const i = document.querySelector('[data-testid="mileage-section"] input[type="text"]');
              Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(i, %s); i.dispatchEvent(new Event('input', {bubbles: true})); })()""" % json.dumps(value))
            submit = lambda: page.js("document.querySelector('[data-testid=\"mileage-section\"] form').requestSubmit()")
            section = lambda: page.js("document.querySelector('[data-testid=\"mileage-section\"]').innerText")
            open_details = lambda: page.js("document.querySelectorAll('details').forEach(d => d.open = true)")
            t = page.text()
            record(tag("mileage: the automatic estimate is selected first"), page.js("document.querySelector('input[name=\"mileage-mode\"][value=\"estimate\"]').checked") is True and "AI-Estimated Mileage" in t and "Model 1 (an XGBoost regression" in t)
            page.shot(f"{mode}_05c_mileage_estimate", "[data-testid='mileage-section']")
            js_click('input[name="mileage-mode"][value="reported"]')
            wait(300)
            t = section()
            record(tag("mileage: option 1 shows the field, the button and no number yet"), "Enter your current mileage (km)" in t and "Use This Mileage" in t and "No mileage entered yet" in t and "AI-Estimated Mileage" not in t)
            for value, expected in (("", "Enter your current mileage in kilometres."), ("-5", "cannot be negative"), ("abc", "digits only"), ("12.5", "digits only"), ("0", "at least 1 km"), ("5000000", "higher than 1,000,000 km")):
                fill(value)
                submit()
                wait(200)
                err = page.js("(document.querySelector('[data-testid=\"mileage-section\"] [role=\"alert\"]') || {}).innerText || ''")
                record(tag(f"mileage: invalid input {value!r} is refused with a clear message"), expected in err and "User-Reported Mileage" not in section(), err)
            page.shot(f"{mode}_05d_mileage_invalid", "[data-testid='mileage-section']")
            fill("123456")
            submit()
            wait(2500)
            t = section()
            record(tag("mileage: a valid value is shown as USER-REPORTED, not verified, not saved"), "User-Reported Mileage" in t and "USER-REPORTED" in t and "123,456 km" in t and "not been verified" in t and "not saved" in t)
            record(tag("mileage: the model note says the risk model uses it as an approximation"), "Risk models:" in t and "Used by Model 2 as the mileage" in t and "approximation" in t)
            open_details()
            full = page.text()
            record(tag("mileage: the risk panel names the user-reported source"), "mileage reported by the user" in full and "Updating the results" not in full)
            record(tag("mileage: no horizontal overflow with a user-reported value"), not page.overflow())
            page.shot(f"{mode}_05e_mileage_user_reported", "[data-testid='mileage-section']")
            fill("900000")
            submit()
            wait(2500)
            t = section()
            record(tag("mileage: an implausible value is shown but flagged as NOT used by the risk model"), "900,000 km" in t and "Not used by the risk model" in t and "per year" in t)
            js_click('input[name="mileage-mode"][value="estimate"]')
            wait(2500)
            t = section()
            full = page.text()
            record(tag("mileage: back to the estimate leaves no user-reported value on screen"), "AI-Estimated Mileage" in t and "User-Reported" not in full and "900,000" not in full and "mileage reported by the user" not in full)
            # switching during a slow request: only the last choice may reach the screen
            page.send("Network.enable")
            page.send("Network.emulateNetworkConditions", offline=False, latency=1500, downloadThroughput=-1, uploadThroughput=-1)
            js_click('input[name="mileage-mode"][value="reported"]')
            fill("111111")
            submit()
            wait(400)
            during = page.js("!!document.querySelector('[data-testid=\"mileage-updating\"]')")
            skeleton = page.js("document.querySelectorAll('[data-testid^=\"risk-\"]').length === 0")
            record(tag("mileage: while the new result loads the screen says so and the old risk panel is not left as current"), during is True and skeleton is True)
            js_click('input[name="mileage-mode"][value="estimate"]')
            wait(6000)
            page.send("Network.emulateNetworkConditions", offline=False, latency=0, downloadThroughput=-1, uploadThroughput=-1)
            wait(500)
            full = page.text()
            record(tag("mileage: switching back during a slow request ends on the estimate (the late answer was discarded)"), "AI-Estimated Mileage" in full and "User-Reported" not in full and "111,111" not in full and "Updating the results" not in full)
            record(tag("mileage: the risk panel is back after the slow switch"), page.js("document.querySelectorAll('[data-testid^=\"risk-\"]').length") == 3)
            common_checks(page, tag("mileage selection"))

            # ---- 3b. Model 1 with too little training data: hybrid aged 9 (Mercedes GLC 350 e)
            page.search("4850581")
            t = page.text()
            low = page.js("!!document.querySelector('[data-testid=\"low-reliability\"]')")
            record(tag("hybrid aged 9: Model 1 flags LOW RELIABILITY with the reason"), low and "Low reliability." in t and "too few hybrid vehicles" in t)
            api = page.js("fetch('http://localhost:8000/api/v1/predict/4850581').then(r => r.json()).then(b => b.mileage)")
            record(tag("hybrid aged 9: no exaggerated yearly mileage is shown"), f"{api['estimated_km']:,} km" in t and api["estimated_annual_km"] < 25_000, str(api["estimated_annual_km"]))
            common_checks(page, tag("hybrid aged 9"))
            page.shot(f"{mode}_04b_low_reliability", "article:has([data-testid='low-reliability'])")

            # ---- 4. NOT covered: electric vehicle (Tesla)
            page.search("88328404")
            t = page.text()
            record(tag("not covered/electric: says why and keeps the other panels"), "has no estimate for this vehicle" in t and "fuel type" in t and "Recommended maintenance" in t and "Open recalls" in t and "AI-Estimated Mileage" in t)
            record(tag("not covered/electric: no risk bars or levels invented"), "RELATIVE RISK" not in t and "Higher than about" not in t)
            record(tag("not covered/electric: mileage flagged low reliability (no electric training data)"), "Low reliability." in t and "electric vehicles" in t)
            record(tag("not covered/electric: no explanation of bars that do not exist"), "How to read this" not in t and "positions in a ranking" not in t)
            common_checks(page, tag("not covered/electric"))
            page.shot(f"{mode}_05_not_covered_electric")
            page.shot(f"{mode}_05b_not_covered_risk_panel", "article:has(h2)")

            # ---- 5. NOT covered: new petrol car (age 0, first annual test not yet taken)
            page.search("62886204")
            t = page.text()
            record(tag("not covered/new car: explained and no bars"), "has no estimate for this vehicle" in t and "RELATIVE RISK" not in t and "first annual inspection" in t.lower())
            page.shot(f"{mode}_06_not_covered_new")

            # ---- 6. official recall (Toyota 2007)
            page.search("1169762")
            t = page.text()
            record(tag("recall: open recall listed as an official fact"), "OPEN RECALL" in t and "not a prediction" in t)
            page.js("[...document.querySelectorAll('section')].find(x => x.querySelector('h2') && x.querySelector('h2').innerText === 'Open recalls').setAttribute('data-shot', '1')")
            page.shot(f"{mode}_07_recall", "[data-shot='1']")

            # ---- 7. anomaly vehicle (60,000 km, no brake service)
            page.search("19319001")
            t = page.text()
            record(tag("anomaly vehicle: brake rule flagged from the measured odometer"), "NO RECORD, OVERDUE" in t and "Recorded odometer" in t and "60,000 km" in t)

            # ---- 8. errors
            page.search("10000001", wait=5)
            record(tag("unknown plate: clear message"), "not found" in page.text().lower())
            page.js("""(async () => { const i = document.querySelector('input[aria-label^="License plate"]');
              Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(i, '123'); i.dispatchEvent(new Event('input', {bubbles: true}));
              document.querySelector('form[role="search"]').requestSubmit(); })()""")
            page.js("new Promise(r => setTimeout(r, 500))")
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
