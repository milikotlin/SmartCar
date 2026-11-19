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
            record(tag("covered/no records: mileage is labelled as an ESTIMATE with a range"), "Estimated mileage" in t and "Indicative range (80%)" in t and "not a measurement" in t)
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
            page.js("document.querySelector('details').open = true")
            t2 = page.text()
            record(tag("covered: details show how levels were set and observed rates"), "How often a defect was found at the next inspection" in t2 and "about" in t2 and "not a forecast for this vehicle" in t2)
            page.shot(f"{mode}_02_risk_details", "article:has([data-testid^='risk-'])")

            # ---- 2. covered, with maintenance records and the last inspection result (seeded demo vehicle)
            page.search("6224652")
            t = page.text()
            record(tag("covered/with records: measured odometer shown as MEASURED and the estimate kept for comparison"), "Odometer (measured)" in t and "Model 1 estimate for comparison" in t)
            record(tag("covered/with records: maintenance rows and inspection result listed"), "[DEMO] Oil and filter change" in t and "ANNUAL INSPECTION RESULTS ON FILE" in t)
            record(tag("covered/with records: the model says the last inspection result is used"), "the last inspection result is used by the risk model" in t)
            record(tag("covered/with records: brake rule flags a missing service"), "NO RECORD, OVERDUE" in t)
            common_checks(page, tag("covered/with records"))
            page.shot(f"{mode}_03_records_full")

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

            # ---- 4. NOT covered: electric vehicle (Tesla)
            page.search("88328404")
            t = page.text()
            record(tag("not covered/electric: says why and keeps the other panels"), "No estimate for this vehicle" in t and "fuel type" in t and "Recommended maintenance" in t and "Open recalls" in t and "Estimated mileage" in t)
            record(tag("not covered/electric: no risk bars or levels invented"), "RELATIVE RISK" not in t and "Higher than about" not in t)
            record(tag("not covered/electric: no explanation of bars that do not exist"), "How to read this" not in t and "positions in a ranking" not in t)
            common_checks(page, tag("not covered/electric"))
            page.shot(f"{mode}_05_not_covered_electric")
            page.shot(f"{mode}_05b_not_covered_risk_panel", "article:has(h2)")

            # ---- 5. NOT covered: new petrol car (age 0, first annual test not yet taken)
            page.search("62886204")
            t = page.text()
            record(tag("not covered/new car: explained and no bars"), "No estimate for this vehicle" in t and "RELATIVE RISK" not in t and "first annual inspection" in t.lower())
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
            record(tag("anomaly vehicle: brake rule flagged from the measured odometer"), "NO RECORD, OVERDUE" in t and "Measured odometer 60,000 km" in t)

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
