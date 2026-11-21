# The limitations of both models in plain language (for the defence)

Golden rule: **state the limitations before anyone asks**. Both models are now built exactly as Smart_Car_Models.pdf specifies (Kaggle datasets pulled with
`kagglehub`); the numbers come from `docs/SPEC_MODELS.md`. The model trained on real UK inspections stays on the dashboard as a comparison.

## Model 1: estimated mileage

**What it is.** It is not the car's odometer. It is an **expected value for similar cars** learned from used-car listings (Kaggle Datasets 7, 8 and 3), using age,
fuel type, make and model, engine size, transmission and number of owners, then adjusted to the Israeli level with the official CBS statistics. One sentence: *"Give me
the car's characteristics and I tell you how far cars like it usually have driven; I do not tell you how far this particular car has driven."*

**How it was built (as the PDF asks).** One-Hot Encoding for fuel, transmission and owner type; Target vs Frequency Encoding for make/model compared by
cross-validation (Frequency won: RMSE 22,155 vs 22,361 km); KNN imputer with K=5; Linear and Ridge regression against Random Forest and XGBoost, chosen purely by RMSE and
MAE: **XGBoost** (held-out RMSE 21,801 km, R² 0.61; Linear/Ridge 24,554 km, R² 0.51). At run time engine size and transmission come from the official model table, the number
of owners from the official ownership history.

**Limitations, in simple words**
1. **It does not hold for an individual car.** The 80% range is wide (it covers 80% of held-out cars), because identical cars drive very different distances.
2. **The data are foreign listings.** UK and Indian cars, listed for sale. The CBS calibration fixes the average level of groups (error 8.6% on the official cells not used
   in the fit), not the error of one car.
3. **Where the data cannot support a figure, the system says so** ("Low reliability"): electric cars, hybrid and gas cars older than 7 years, and combinations whose
   estimate would mean more than 40,000 km a year. In that last case the **official CBS average for that age and ownership is shown instead** of the model's number
   (example: a 2025 diesel leasing car got 93,000 km a year from the model; 36,500 is shown).
4. **A dataset label did not mean what the PDF says.** Dataset 8 `Owner_Type` is the number of owners (First, Second...), not private/leasing. It is used as such.

## Model 2: risk of a mechanical failure needing maintenance

**What it is.** A score learned from Kaggle Dataset 1 (logistics vehicles, synthetic labels), enriched with the failure distribution of Dataset 4; electric and
hybrid cars use a separate model on Dataset 5. It is shown as **three levels** (Low, Moderate, High), never as a percentage.

**How it was built (as the PDF asks).** Sensor columns removed; Vehicle_Age, Days_Since_Last_Maintenance and a Brand_Reliability_Index; the mileage from Model 1;
SMOTE against scale_pos_weight (scale_pos_weight won); XGBoost against Logistic Regression (XGBoost 0.978 vs 0.943 ROC-AUC on held-out Dataset 1); tuning to maximise Recall.

**Limitations, in simple words (the most important part of the defence)**
1. **The labels are synthetic.** On its own data the model looks excellent (ROC-AUC 0.978), but it learned the dataset's rules: almost all of its power comes from
   "days since the last maintenance" (0.87 alone) and "past failures" (0.77 alone). Age, mileage and brand are near 0.5 (no information).
2. **On real inspections it is worse than age alone.** Checked on 150,000 real UK inspection outcomes: **0.585**, while simply ordering cars by age gives **0.646** and
   the comparison model trained on real inspections gives 0.68 to 0.72. Example: it puts a 2022 Hyundai i20 at Moderate and a 2014 Nissan Micra at Low; the
   comparison model puts the older Micra higher.
3. **Without a service log it says little.** Its two strong inputs come from the maintenance and inspection records; without them it uses typical values, and the
   panel says so ("What this level is worth here").
4. **The electric/hybrid model has no predictive power.** On its own test data ROC-AUC 0.49 (chance); the panel says the level carries no information.
5. **Forced decisions, all documented:** the augmented third Dataset 1 file was excluded (near-duplicates of test rows); leaky columns removed; Dataset 4 has no age
   column (grouped by mileage only); the brand index comes from real UK inspection outcomes (no Kaggle dataset measures it); Recall tuning guarded against "flag
   every car"; a monotone constraint (more past failures never lower the risk) fixed an artefact of mixing two Dataset 1 generators.

**In one honest sentence:** *"I implemented Model 2 exactly as specified and measured it on real data: it learned its synthetic dataset very well, but on real inspections
it ranks cars worse than their age, so I show it as relative levels, explain what each level is worth, and keep the model trained on real inspections next to it."*

## The comparison model (real inspections)
XGBoost per system trained on real UK MOT inspections and validated on Dutch ones; ROC-AUC 0.68 to 0.72; most of its level is the age of the car; it adds more when the
previous inspection result or the odometer is known (`docs/MODEL2_VS_AGE_BASELINE.md`). Not validated on Israeli cars (Israeli results are not open data).

## System security, in three sentences
Reading is open; writing records requires a **workshop key** (a stored inspection result is an input of the models, so anyone could otherwise change the risk of somebody
else's car). The key lives only in `.env` (never in the browser or in git), with a rate limit, a limit on records per car and date validation. It is deliberately simple (no
login, as the SRS requires): it proves "an authorised workshop", not *who* wrote the record.

## Hard questions, short answers
* **"Why is Model 2 so good on its data and so weak on real cars?"** — Because its labels were generated by rules (synthetic). It learned those rules (0.978) but real
  failures do not follow them (0.585 on real inspections).
* **"Then why use it?"** — The specification requires it, and it is implemented exactly. The measurement on real data is the honest part: it is why the levels are
  relative, why the panel explains their worth, and why the real-inspection model stays next to it.
* **"Does this predict breakdowns?"** — No. Model 2 imitates a synthetic "maintenance required" label; the comparison model predicts a defect at the next annual
  inspection. Neither is a breakdown probability.
* **"Does it work in Israel?"** — Neither model has been validated on Israeli cars; the data that would allow it (inspection results, individual odometers) are not open.
* **"Is the mileage right?"** — It is an expected value for similar cars, calibrated to official averages, with a wide range; when the model would exaggerate, the official
  average is shown instead and flagged.
