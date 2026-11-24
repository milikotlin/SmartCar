"""Browser checks of the two languages and of the "Nearby Garages" section (run by scripts/visual_check.py, desktop and phone)."""
import json
import re

API = "http://localhost:8000/api/v1"
ORIGIN = "http://localhost:3000"
CARD = "[data-testid='garage-card']"

# words of the English interface that must not be left when the interface is in Hebrew
ENGLISH_WORDS = ("Look up", "Age", "Mileage", "Moderate", "Low", "High", "Every", "No record", "Recommended", "Service", "Inspection", "Date", "Cost", "Save", "Vehicle", "Garages", "City", "Radius", "Search",
                 "Approximate", "Brakes", "percentile", "Estimated", "Private", "Petrol", "White", "Real", "Model")

FIGURES = r"""[...document.querySelectorAll('[data-testid="mileage-section"], [data-testid="failure-risk"], [data-testid="comparison-risk"]')]
  .map(e => (e.innerText.match(/\d[\d,.]*\d|\d/g) || []).sort().join()).join('|')"""
LEVEL = r"""[...document.querySelectorAll('[data-testid="failure-risk"] .h-4 > div')].map(e => /bg-(ok|warn|critical)( |$)/.test(e.className)).join()"""
VISIBLE_TEXT = r"""(() => [...document.querySelectorAll('[placeholder],[aria-label],[title]')].filter(e => !e.closest('.leaflet-container') && !e.closest('[data-locale]'))
  .map(e => [e.placeholder, e.ariaLabel, e.title].join(' ')).join(' ') + ' ' + document.body.innerText)()"""
BARS = r"""[...document.querySelectorAll('[data-testid^="risk-"]')].map(c => { const bar = c.querySelector('[role="img"]'); const b = bar.getBoundingClientRect(), m = bar.querySelector(':scope > .absolute').getBoundingClientRect();
  return [Math.abs((b.right - (m.left + m.right) / 2) / b.width * 100 - Number(c.innerText.match(/P(\d+)/)[1])) < 2]; }).flat()"""
MIRRORED = r"""(() => { const card = document.querySelector('[data-testid="mileage-section"]').closest('article').getBoundingClientRect(), risk = document.querySelector('[data-testid="failure-risk"]').getBoundingClientRect(),
  fab = document.querySelector('button[aria-expanded][aria-label]').getBoundingClientRect(); return {card: card.left, risk: risk.left, fab: fab.left, wide: innerWidth >= 1025}; })()"""
DISTANCES = r"""[...document.querySelectorAll("[data-testid='garage-card']")].map(c => (c.innerText.match(/([\d.]+) km/) || [])[1]).filter(Boolean).map(Number)"""


def wait(page, ms):
    page.js("new Promise(r => setTimeout(r, %d))" % ms)


def click(page, selector):
    page.js("document.querySelector(%s).click()" % json.dumps(selector))


def text(page, selector, prop="innerText"):
    return page.js("(document.querySelector(%s) || {}).%s || ''" % (json.dumps(selector), prop))


def count(page, selector):
    return page.js("document.querySelectorAll(%s).length" % json.dumps(selector))


def fill(page, selector, value):
    page.js("""(() => { const i = document.querySelector(%s), select = i.tagName === 'SELECT';
      Object.getOwnPropertyDescriptor((select ? HTMLSelectElement : HTMLInputElement).prototype, 'value').set.call(i, %s);
      i.dispatchEvent(new Event(select ? 'change' : 'input', {bubbles: true})); })()""" % (json.dumps(selector), json.dumps(value)))


def choose_option(page, code=None):
    selector = "[role=option]" + (f"[data-city='{code}']" if code else "")
    for _ in range(20):                                      # the suggestions come from the server
        if count(page, selector):
            break
        wait(page, 400)
    page.js("document.querySelector(%s).dispatchEvent(new MouseEvent('mousedown', {bubbles: true}))" % json.dumps(selector))


def direction(page):
    return page.js("document.documentElement.lang + ' ' + document.documentElement.dir")


def language_checks(page, tag, mode, record):
    """English <-> Hebrew with a vehicle on the screen: direction, every text, same figures, memory of the choice."""
    page.open()
    wait(page, 2000)
    record(tag("language: English is the default"), direction(page) == "en ltr")
    record(tag("language: visible selector with both languages"), "English" in text(page, "button[data-locale='en']") and "עברית" in text(page, "button[data-locale='he']"))
    page.search("6224652")
    figures, level = page.js(FIGURES), page.js(LEVEL)
    click(page, "button[data-locale='he']")
    wait(page, 5000)
    record(tag("Hebrew: lang and right-to-left direction"), direction(page) == "he rtl")
    t = page.text()
    record(tag("Hebrew: the vehicle stays on the screen, registry values in Hebrew"), "6224652" in t and all(w in t for w in ("שנה", "דלק", "בעלות", "טיפולים מומלצים", "ריקולים פתוחים", "יומן טיפולים", "מוסכים קרובים", "משרד התחבורה")))
    record(tag("Hebrew: same figures and same risk level"), page.js(FIGURES) == figures and page.js(LEVEL) == level and len(figures) > 30, f"{figures} / {page.js(FIGURES)}")
    page.js("document.querySelectorAll('details').forEach(d => d.open = true)")
    wait(page, 400)
    t = page.js(VISIBLE_TEXT)
    left = [w for w in ENGLISH_WORDS if re.search(rf"(?<![\w-]){w}(?![\w-])", t)]
    record(tag("Hebrew: no interface text left in English"), not left, str(left))
    record(tag("Hebrew: no horizontal overflow"), not page.overflow())
    g = page.js(MIRRORED)
    record(tag("Hebrew: the layout is mirrored"), g["fab"] < 60 and (g["card"] > g["risk"] or not g["wide"]), str(g))
    record(tag("Hebrew: the plate stays left-to-right"), page.js("getComputedStyle(document.querySelector('article span[dir=\"ltr\"]')).direction") == "ltr")
    bars = page.js(BARS)
    record(tag("Hebrew: gauge markers are mirrored too"), len(bars) == 3 and all(bars), str(bars))
    page.shot(f"{mode}_10_hebrew_full")

    click(page, "button[aria-label^='פתיחת עוזר']")
    wait(page, 600)
    fill(page, "input[aria-label='תיאור תסמין']", "נשמעת חריקה בבלמים")
    page.js("document.querySelector(\"input[aria-label='תיאור תסמין']\").closest('form').requestSubmit()")
    wait(page, 5000)
    dialog = text(page, "[role=dialog]")
    record(tag("Hebrew: the chat answers in Hebrew"), "מכונאי מוסמך" in dialog and "תשובה לפי כללים" in dialog and "Brake symptoms" not in dialog, dialog[:200])
    page.shot(f"{mode}_11_hebrew_chat", viewport=True)
    click(page, "button[aria-label^='סגירת עוזר']")

    fill(page, "input[aria-label^='מספר רישוי']", "123")
    page.js("document.querySelector('form[role=\"search\"]').requestSubmit()")
    wait(page, 400)
    record(tag("Hebrew: validation message"), "יש להזין 7 או 8 ספרות" in page.text())

    page.open()
    wait(page, 2000)
    record(tag("language: the choice is remembered on the next visit"), direction(page) == "he rtl" and "חיפוש רכב" in page.text())
    record(tag("language: the page already arrives in Hebrew (no English flash)"), page.js("fetch('/').then(r => r.text()).then(h => h.includes('dir=\"rtl\"') && h.includes('חיפוש רכב'))"))
    click(page, "button[data-locale='en']")
    wait(page, 4000)
    record(tag("language: back to English, left-to-right"), direction(page) == "en ltr" and "Look up a vehicle" in page.text())


def garage_checks(page, tag, mode, record):
    """Nearby garages: city in two languages, real results, map, links, GPS with and without permission, empty, loading and error states."""
    page.open()
    wait(page, 2500)
    record(tag("garages: section and header link on the first screen"), "Nearby Garages" in page.text() and count(page, "header a[href='#garages']") == 1 and "Choose a city or use your location" in page.text())
    fill(page, "[data-testid='garage-city']", "petah tik")
    wait(page, 2000)
    record(tag("garages: suggestions for an English name"), "Petah Tikva" in text(page, "[role=listbox]") and "פתח תקווה" in text(page, "[role=listbox]"))
    choose_option(page, 7900)
    wait(page, 5500)
    api = page.js(f"fetch('{API}/garages?city=7900').then(r => r.json())")
    summary = text(page, "[data-testid='garage-summary']")
    record(tag("garages: real results of the official register"), f"{api['total_in_city']} garages in Petah Tikva" in summary and count(page, CARD) == 20, summary)
    g, first = api["items"][0], text(page, CARD)
    record(tag("garages: name, address, city, distance and phone"), all(x in first for x in (g["name"], g["address"], "Petah Tikva", g["phone"], "km")), first)
    record(tag("garages: says that a city search is approximate"), "Approximate results for the Petah Tikva area" in text(page, "[data-testid='garage-note']"))
    links = page.js("[...document.querySelector(%s).querySelectorAll('a')].map(a => [a.href, a.target, a.rel])" % json.dumps(CARD))
    record(tag("garages: Google Maps, Waze and phone links"), any(h.startswith("https://www.google.com/maps/dir/") and t == "_blank" and "noopener" in r for h, t, r in links)
           and any(h.startswith("https://waze.com/ul?") for h, _, _ in links) and any(h.startswith("tel:") for h, _, _ in links), str(links))
    tiles = page.js("[...document.querySelectorAll('.leaflet-tile')].filter(t => t.complete && t.naturalWidth > 0).length")
    record(tag("garages: map with tiles, pins and attribution"), tiles > 0 and count(page, ".garage-pin") > 3 and "OpenStreetMap" in text(page, ".leaflet-control-attribution"), str(tiles))
    click(page, ".leaflet-marker-icon")
    wait(page, 1000)
    record(tag("garages: a pin selects its garage"), page.js("[...document.querySelectorAll(%s)].some(c => c.className.includes('border-accent'))" % json.dumps(CARD)))
    record(tag("garages: no rating is invented"), "★" not in text(page, "[data-testid='garages']"))
    record(tag("garages: no horizontal overflow"), not page.overflow())
    page.shot(f"{mode}_12_garages", "[data-testid='garages']")
    click(page, "[data-testid='garage-more']")
    wait(page, 2500)
    record(tag("garages: 'show more' adds results"), count(page, CARD) == 40)
    fill(page, "[data-testid='garage-service']", "ev_hybrid")
    wait(page, 2500)
    record(tag("garages: service filter"), count(page, CARD) > 0 and page.js("[...document.querySelectorAll(%s)].every(c => c.innerText.includes('EV / hybrid'))" % json.dumps(CARD)))
    fill(page, "[data-testid='garage-city']", "Atlantis")
    wait(page, 2000)
    record(tag("garages: an unknown city says so"), "No city with that name" in text(page, "[data-testid='garage-city-unknown']"))

    fill(page, "[data-testid='garage-service']", "gearbox")
    fill(page, "[data-testid='garage-radius']", "5")
    fill(page, "[data-testid='garage-city']", "מצפה רמון")
    wait(page, 2000)
    choose_option(page)
    wait(page, 2500)
    record(tag("garages: 'no results' state"), "No licensed garage found here" in text(page, "[data-testid='garage-empty']"))
    fill(page, "[data-testid='garage-service']", "")
    wait(page, 300)
    fill(page, "[data-testid='garage-radius']", "10")
    wait(page, 1500)

    page.send("Network.enable")
    page.send("Network.setBlockedURLs", urls=["*/api/v1/garages?city=*"])
    click(page, "button[data-popular-city='4000']")
    wait(page, 1500)
    record(tag("garages: error state"), "could not be loaded" in text(page, "[data-testid='garage-error']"))
    page.send("Network.setBlockedURLs", urls=[])
    click(page, "[data-testid='garage-error'] button")
    wait(page, 3000)
    record(tag("garages: 'try again' works"), "in Haifa" in text(page, "[data-testid='garage-summary']"))
    page.send("Network.emulateNetworkConditions", offline=False, latency=1500, downloadThroughput=-1, uploadThroughput=-1)
    click(page, "button[data-popular-city='3000']")
    wait(page, 400)
    record(tag("garages: loading state"), count(page, "[data-testid='garage-loading']") == 1)
    wait(page, 4500)
    page.send("Network.emulateNetworkConditions", offline=False, latency=0, downloadThroughput=-1, uploadThroughput=-1)

    page.send("Browser.setPermission", permission={"name": "geolocation"}, setting="denied", origin=ORIGIN)
    click(page, "[data-testid='garage-gps']")
    wait(page, 1500)
    record(tag("garages: location refused -> clear message, results kept"), "not allowed" in text(page, "[data-testid='garage-geo-error']") and "in Jerusalem" in text(page, "[data-testid='garage-summary']"))
    page.send("Browser.setPermission", permission={"name": "geolocation"}, setting="granted", origin=ORIGIN)
    page.send("Emulation.setGeolocationOverride", latitude=48.85, longitude=2.35, accuracy=20)
    click(page, "[data-testid='garage-gps']")
    wait(page, 1500)
    record(tag("garages: a position outside Israel is refused"), "outside Israel" in text(page, "[data-testid='garage-geo-error']"))
    page.js("window.__bodies = []; const f = window.fetch; window.fetch = (u, o) => { if (String(u).includes('/garages')) window.__bodies.push([String(u), o && o.method]); return f(u, o); }; 0")
    page.send("Emulation.setGeolocationOverride", latitude=32.0158, longitude=34.7874, accuracy=20)
    wait(page, 300)
    click(page, "[data-testid='garage-gps']")
    wait(page, 4500)
    near = page.js("window.__bodies")
    if not any("/near" in u for u, _ in near):              # the earlier position may still be cached by the browser for a minute
        wait(page, 61_000)
        click(page, "[data-testid='garage-gps']")
        wait(page, 4500)
        near = page.js("window.__bodies")
    d = page.js(DISTANCES)
    record(tag("garages: location allowed -> sorted by the real distance"), "within 10 km of you" in text(page, "[data-testid='garage-summary']") and len(d) == 20 and d == sorted(d) and "not stored" in text(page, "[data-testid='garage-note']"), str(d))
    record(tag("garages: own position is drawn on the map"), count(page, ".garage-pin.is-you") == 1)
    record(tag("garages: the position travels in the body only and is not stored"), any("/near" in u and m == "POST" for u, m in near) and not any("32.01" in u or "34.78" in u for u, _ in near)
           and "32.01" not in page.js("location.href + document.cookie + JSON.stringify(localStorage) + JSON.stringify(sessionStorage)"), str(near))

    click(page, "button[data-locale='he']")
    wait(page, 4500)
    t = text(page, "[data-testid='garages']")
    record(tag("garages: Hebrew, right-to-left, results kept"), all(x in t for x in ("מוסכים קרובים", "המיקום שלי", "ממך", "רדיוס", "שירות")) and "Nearby" not in t and " km" not in t and not page.overflow())
    fill(page, "[data-testid='garage-city']", "הרצליה")
    wait(page, 2000)
    choose_option(page, 6400)
    wait(page, 4500)
    record(tag("garages: Hebrew city search"), "בהרצליה" in text(page, "[data-testid='garage-summary']") and "תוצאות מקורבות" in text(page, "[data-testid='garage-note']"))
    page.shot(f"{mode}_13_garages_hebrew", "[data-testid='garages']")
    click(page, "button[data-locale='en']")
    wait(page, 4000)
    record(tag("garages: the city name follows the language"), text(page, "[data-testid='garage-city']", "value") == "Herzliya" and "in Herzliya" in text(page, "[data-testid='garage-summary']"))
