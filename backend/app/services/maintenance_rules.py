"""Rule-based maintenance schedule (SRS "deterministic fallback", section 3).

These are GENERIC service intervals commonly published by manufacturers for passenger cars. They are NOT learned from data, NOT specific to the
make and model of the vehicle (the owner's manual prevails) and are never shown as a probability. Status is computed from the vehicle's own
service records in the database (time and kilometres since the last service of the same kind).
"""
from dataclasses import dataclass
from datetime import date

KEYWORDS = {
    "oil": ("oil", "שמן"),
    "brakes": ("brake pad", "brake disc", "brake", "בלם", "בלמים", "רפידות"),
    "brake_fluid": ("brake fluid", "נוזל בלמים"),
    "tires": ("tire", "tyre", "צמיג"),
    "coolant": ("coolant", "antifreeze", "נוזל קירור"),
    "battery": ("battery", "מצבר"),
    "filters": ("air filter", "cabin filter", "filter", "מסנן"),
}


@dataclass(frozen=True)
class Rule:
    key: str
    label: str
    months: int | None
    km: int | None
    skip_for_fuels: tuple[str, ...] = ()
    min_vehicle_age: int = 0
    advice: str = ""


RULES = [
    Rule("oil", "Engine oil and oil filter", 12, 15_000, ("electric",), 0, "Change engine oil and filter."),
    Rule("brakes", "Brake system inspection (pads, discs, lines)", 12, 30_000, (), 0, "Have pads, discs, lines and fluid level inspected."),
    Rule("brake_fluid", "Brake fluid replacement", 24, None, (), 0, "Replace brake fluid (absorbs moisture over time)."),
    Rule("tires", "Tyre inspection (tread, pressure, age)", 12, 20_000, (), 0, "Check tread depth, pressure and sidewalls."),
    Rule("coolant", "Coolant replacement", 60, 100_000, (), 3, "Replace coolant per the owner's manual."),
    Rule("battery", "12 V battery test", 12, None, (), 4, "Test the battery; weak batteries are a common cause of lighting and electrical faults."),
    Rule("filters", "Air and cabin filters", 12, 20_000, (), 0, "Replace air and cabin filters."),
]
DISCLAIMER = "Generic service intervals, not specific to this make and model and not learned from data; the owner's manual prevails."


def classify_record(category: str | None, description: str | None) -> str | None:
    """Map a maintenance record to a rule key from its category, else from keywords in the description."""
    cat = (category or "").strip().lower()
    if cat in {r.key for r in RULES}:
        return cat
    text = f"{cat} {(description or '').lower()}"
    for key in ("brake_fluid", "oil", "coolant", "battery", "tires", "filters", "brakes"):        # specific before generic
        if any(k in text for k in KEYWORDS[key]):
            return key
    return None


def _months_between(a: date, b: date) -> float:
    return max((b - a).days / 30.4375, 0.0)


def evaluate(records: list[dict], today: date, fuel: str, vehicle_age: int, odometer_km: int | None, odometer_measured: bool) -> list[dict]:
    """records: [{"service_date": date, "mileage_at_service": int, "description": str, "maintenance_category": str|None}]"""
    latest: dict[str, dict] = {}
    for r in sorted(records, key=lambda r: r["service_date"]):
        key = classify_record(r.get("maintenance_category"), r.get("description"))
        if key:
            latest[key] = r
    out = []
    for rule in RULES:
        if fuel in rule.skip_for_fuels or vehicle_age < rule.min_vehicle_age:
            continue
        interval = " or ".join(x for x in (f"{rule.months} months" if rule.months else "", f"{rule.km:,} km" if rule.km else "") if x)
        item = {"key": rule.key, "label": rule.label, "interval": interval, "advice": rule.advice, "last_service_date": None, "last_service_km": None, "months_since": None, "km_since": None,
                "status": "no_record", "attention": False, "basis": None, "source": "maintenance_rule"}
        rec = latest.get(rule.key)
        if rec:
            months = _months_between(rec["service_date"], today)
            item.update({"last_service_date": rec["service_date"].isoformat(), "last_service_km": rec["mileage_at_service"], "months_since": round(months, 1)})
            ratios = [months / rule.months] if rule.months else []
            if rule.km and odometer_km is not None and rec.get("mileage_at_service") is not None:
                km_since = max(odometer_km - rec["mileage_at_service"], 0)
                item["km_since"] = km_since
                ratios.append(km_since / rule.km)
                item["basis"] = "time and measured odometer" if odometer_measured else "time and estimated odometer"
            else:
                item["basis"] = "time only"
            ratio = max(ratios) if ratios else 0.0
            item["status"] = "overdue" if ratio >= 1 else ("due_soon" if ratio >= 0.8 else "ok")
            item["attention"] = item["status"] in ("overdue", "due_soon")
        else:
            # no service of this kind on record: flag it only when a MEASURED odometer or the age proves the interval has passed
            passed_km = bool(rule.km and odometer_km is not None and odometer_measured and odometer_km >= rule.km)
            passed_time = bool(rule.months and vehicle_age * 12 >= rule.months)
            if passed_km:
                item.update({"status": "no_record_overdue", "attention": True, "basis": f"measured odometer {odometer_km:,} km with no {rule.label.lower()} on record"})
            elif passed_time:
                item.update({"status": "no_record", "basis": f"vehicle is {vehicle_age} years old; no {rule.label.lower()} on record"})
        out.append(item)
    return out
