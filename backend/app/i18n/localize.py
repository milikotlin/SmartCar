"""Final step of an answer: adds language-independent codes and, for Hebrew, replaces the texts. Numbers, levels, inputs and flags are never touched (tests/test_i18n.py)."""
from app.i18n import Lang
from app.i18n import domain as d
from app.schemas.prediction import PredictionResponse
from app.schemas.vehicle import VehicleProfile
from app.services.maintenance_rules import RULES

_RULES = {r.key: r for r in RULES}


def localize_vehicle(v: VehicleProfile, lang: Lang) -> VehicleProfile:
    if lang == "en":
        return v
    return v.model_copy(update={"make": d.make_he(v.make, v.make_raw), "fuel_type": d.FUEL.get(v.fuel_type, v.fuel_type), "ownership": d.OWNERSHIP.get(v.ownership, v.ownership),
                                "color": v.color_raw or v.color})


def _add_codes(p: PredictionResponse) -> None:
    p.mileage.estimate_reliability_code = d.code(p.mileage.estimate_reliability_reason)
    p.inspection_risk.reason_codes = [d.code(r) for r in p.inspection_risk.reasons]
    p.maintenance.odometer_basis_code = d.code(p.maintenance.odometer_basis)
    for r in p.maintenance.rules:
        rule = _RULES[r.key]
        r.interval_months, r.interval_km = rule.months, rule.km


def localize_prediction(prediction: PredictionResponse, lang: Lang) -> PredictionResponse:
    """A copy of the answer in the requested language. English texts stay exactly as the pipeline wrote them."""
    p = prediction.model_copy(deep=True)
    _add_codes(p)
    if lang == "en":
        return p
    p.vehicle = localize_vehicle(p.vehicle, lang)
    m = p.mileage
    m.notes = [d.he(n) for n in m.notes]
    m.label, m.estimate_reliability_reason, m.user_reported_note = d.he(m.label), d.he(m.estimate_reliability_reason), d.he(m.user_reported_note)
    if "engine_and_transmission_source" in m.model_inputs:
        m.model_inputs["engine_and_transmission_source"] = d.he(m.model_inputs["engine_and_transmission_source"])
    r = p.inspection_risk
    r.definition, r.disclaimer, r.reasons = d.he(r.definition), d.he(r.disclaimer), [d.he(x) for x in r.reasons]
    for s in r.systems:
        s.title, s.explanation = d.he(s.title), d.he(s.explanation)
    if r.scale:
        c = r.scale
        c.reference, c.interval, c.country_note = d.he(c.reference), d.he(c.interval), d.he(c.country_note)
        c.level_rule = {k: d.he(v) for k, v in c.level_rule.items()}
    f = p.failure_risk
    if f:
        f.definition, f.branch_label, f.level_rule, f.quality_note, f.disclaimer = (d.he(x) for x in (f.definition, f.branch_label, f.level_rule, f.quality_note, f.disclaimer))
        f.assumed = [d.he(a) for a in f.assumed]
        for row in f.comparison:
            row.model, row.data, row.test = d.he(row.model), d.he(row.data), d.he(row.test)
    mt = p.maintenance
    mt.disclaimer, mt.odometer_basis = d.he(mt.disclaimer), d.he(mt.odometer_basis)
    for x in mt.rules:
        x.label, x.advice, x.interval, x.basis = d.RULE_LABEL[x.key], d.RULE_ADVICE[x.key], d.he(x.interval), d.he(x.basis)
    p.recalls.source, p.recalls.error = d.he(p.recalls.source), d.he(p.recalls.error)
    for i in p.recalls.items:
        i.type, i.category = d.RECALL_TYPE.get(i.type, i.type), d.RECALL_CATEGORY.get(i.category, i.category)
    p.history.note = d.he(p.history.note)
    p.provenance.notes = [d.he(n) for n in p.provenance.notes]
    return p
