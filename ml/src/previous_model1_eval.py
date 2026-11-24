"""The PREVIOUS Model 1 (commit 3c539da) judged on the same REAL odometers as the new one (random official test vehicles). Writes ml/previous_model1_on_real_odometers.json."""
import json
import joblib
from m1_lab import *  # noqa: F401,F403
from calibration import MAX_AGE  # noqa: F401
import cbs_reference as cbs

prev = Path.home() / "smartcar_data" / "interim" / "previous_spec"
pipe = joblib.load(prev / "model1_pipeline.joblib")
cal_prev = json.loads((prev / "model1_calibration.json").read_text(encoding="utf-8"))
o = odometers()
t = o[o.part == "test"].sample(6000, random_state=0).reset_index(drop=True)
X = t[M1_FEATURES].copy()
X.loc[X.engine_cc == 0, "engine_cc"] = np.nan
Xu = X.drop_duplicates().reset_index(drop=True)
pu = np.clip(pipe.predict(Xu), 0, None)
p = X.merge(Xu.assign(p=pu), on=list(X.columns), how="left").p.to_numpy()
out = {"n": len(t), "all": metrics(t.km, p), "by_age": {}, "by_fuel": {}}
for lo, hi in ((1, 3), (4, 6), (7, 9), (10, 13), (14, 25)):
    k = t.age.between(lo, hi).to_numpy()
    out["by_age"][f"{lo}-{hi}"] = metrics(t.km[k], p[k])
for f in t.fuel.unique():
    k = (t.fuel == f).to_numpy()
    if k.sum() > 30:
        out["by_fuel"][f] = metrics(t.km[k], p[k])
q = [cal_prev["residual_ratio_quantiles"][cbs.age_to_band(a)] for a in t.age]
out["interval_80pct_coverage"] = float(np.mean([(p[i] * q[i][0] <= t.km[i] <= p[i] * q[i][1]) for i in range(len(t))]))
(ROOT / "ml" / "previous_model1_on_real_odometers.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(out["all"], out["interval_80pct_coverage"])
