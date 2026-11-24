# The limitations of both models in plain language (for the defence)

Golden rule: **state the limitations before anyone asks**. Both models follow Smart_Car_Models.pdf (Kaggle datasets pulled with `kagglehub`); version 3.0.0 adds data
augmentation and is judged only on real data. The numbers come from `docs/SPEC_MODELS.md`.

## Model 1: estimated mileage

**What it is.** It is not the car's odometer. It is an **expected value for similar cars**, using age, fuel, make and model, engine size, transmission and number of owners, adjusted to
the Israeli level with the official CBS statistics. One sentence: *"Give me the car's characteristics and I tell you how far cars like it usually have driven; I do not tell you how far this
particular car has driven."*

**How it was built (as the PDF asks).** Datasets 7, 8 and 3; One-Hot Encoding; Target vs Frequency Encoding (Frequency won); KNN imputer with K=5; Linear and Ridge regression against Random
Forest and XGBoost, chosen by RMSE and MAE: **XGBoost**. Training adds 250,000 **synthetic** vehicles generated from real odometers (training only).

**What improved.** On the same 6,000 **real odometers**: RMSE 67,855 -> **47,969 km**, MAE 47,762 -> **34,711 km**, R² 0.119 -> **0.560**.
On the Kaggle listings it is unchanged (RMSE 21,801 -> 21,878; R² 0.609 -> 0.607). The "80%" range now really holds 80% of real
odometers (before 53%), and the error against the official Israeli averages fell from 8.6% to 3.9%.

Fair baseline: a plain table of age and fuel reaches RMSE 50,165 km and R² 0.518 on real odometers; the model 47,410 km and 0.569. Most of the information is age and fuel. These are UK cars:
in Israel the improvement that can be checked is the smaller error against the official averages.

**Limitations, in simple words**
1. **It does not hold for an individual car.** An R² of 0.56 on real cars means a lot of the difference between two identical cars stays unexplained; the range shows it.
2. **Israel publishes no odometers.** The Israeli level is official (CBS); the error for one Israeli car cannot be measured.
3. **Make and model move the Israeli estimate only a little** (lambda = 0.1): their effect was tested on two foreign markets and did not transfer, so it is shrunk on purpose.
4. **Where the data cannot support a figure, the system says so** ("Low reliability"): electric cars (no CBS figure), hybrids older than 8 years (the real UK ones are mostly former taxis),
   groups with fewer than 100 real vehicles, and more than 40,000 km a year, where the **official average** for the age and ownership is shown instead.
5. **A dataset label did not mean what the PDF says.** Dataset 8 `Owner_Type` is the number of owners (First, Second...), not private/leasing. It is used as such.

## Model 2: risk of a mechanical failure needing maintenance

**What it is.** A score for "a defect is found at the next annual inspection" (the only real outcome available), from age, mileage (Model 1), maintenance and failure history, brand and the
Dataset 4 failure distribution. Combustion and electric / hybrid vehicles have separate branches (Dataset 1 / Dataset 5). Shown as **three levels**, never as a percentage.

**How it was built (as the PDF asks).** Sensors dropped; SMOTE against scale_pos_weight (scale_pos_weight won: SMOTE was slightly worse on real cars); XGBoost against Logistic Regression; tuning that maximises Recall.
Training rows: Kaggle plus synthetic vehicles generated from real inspections. Every choice and every figure comes from **real vehicles never used in training**.

**What improved** (real UK vehicles, riskiest 40% flagged, mean of four situations): Recall 0.447 -> **0.577**, Precision 0.334 -> **0.432**, ROC-AUC
0.567 -> **0.674**. The levels are real: 16% / 29% / 45% of Low / Moderate / High vehicles had a defect.

**Say this yourself: the earlier 0.978 was wrong.** Version 2.0.0 reported ROC-AUC 0.978 on Dataset 1. It was **data leakage**: in that file `Maintenance_Type` gives the label exactly, and
"more than 180 days since the last maintenance" *is* the label. The model had copied the rule; on real cars it was close to chance. The column was removed, the rule limited, and the figure withdrawn.

**Limitations, in simple words**
1. **About 0.67, not 0.97.** Inspection defects are hard to predict from a plate. With only the plate the gain over age alone is small but real (+0.015 ROC-AUC, 95% interval +0.014 to +0.017);
   with the odometer and the last inspection the model reaches 0.688 (age alone 0.646).
2. **The electric / hybrid branch is not better than age alone when only the plate is known** (+0.003, interval -0.013 to +0.018): Dataset 5 carries no signal after the strict dropping and there are few real electric cars.
3. **The Dutch check** gives 0.652 (age alone 0.642): the order of risk transfers, the absolute rates do not, hence levels and not percentages.
4. **Services are learned from rule-generated labels.** No real data set links a service log to failures, so "days since the last maintenance" has a limited weight.
5. **Vehicles under 3 or over 20 years** are outside the real data: the level is an extrapolation (the API says so), but more age or kilometres can never lower the risk.

**In one honest sentence:** *"I found leakage in my own first result, removed it, trained with synthetic vehicles that imitate real ones, and measured everything on real vehicles the models had
never seen: the numbers are lower than before and, this time, true."*

## The comparison model (real inspections)
XGBoost per system trained on real UK MOT inspections and validated on Dutch ones; ROC-AUC 0.68 to 0.72; most of its level is the age of the car; it adds more when the
previous inspection result or the odometer is known (`docs/MODEL2_VS_AGE_BASELINE.md`). Not validated on Israeli cars (Israeli results are not open data).

## System security, in three sentences
Reading is open; writing records requires a **workshop key** (a stored inspection result is an input of the models, so anyone could otherwise change the risk of somebody
else's car). The key lives only in `.env` (never in the browser or in git), with a rate limit, a limit on records per car and date validation. It is deliberately simple (no
login, as the SRS requires): it proves "an authorised workshop", not *who* wrote the record.

## Hard questions, short answers
* **"Why did the ROC-AUC fall from 0.978 to 0.67?"** - Because 0.978 was leakage (the label was a rule on two input columns). On real cars that model scored 0.57; this one scores 0.67.
* **"Is training on synthetic data cheating?"** - No: synthetic rows are only in training, they come from a part of the vehicles used for nothing else, and every result is on real vehicles.
  Training on the real rows instead gives the same result, which shows the synthetic ones are faithful.
* **"Does this predict breakdowns?"** — No. Both Model 2 and the comparison model rank the risk that the next annual inspection finds a defect. Neither is a breakdown probability.
* **"Does it work in Israel?"** — Neither model has been validated on Israeli cars; the data that would allow it (inspection results, individual odometers) are not open.
* **"Is the mileage right?"** — It is an expected value for similar cars, calibrated to official averages, with a wide range; when the model would exaggerate, the official
  average is shown instead and flagged.
