# The limitations of both models in plain language (for the defence)

Golden rule: **state the limitations before anyone asks**. Every number below comes from the project files (where to check it is in parentheses).

## Model 1: estimated mileage

**What it is.** It is not the car's odometer. It is an **expected average for similar cars** (same age, fuel type and ownership type), adjusted to the Israeli level with the official CBS statistics. One sentence for the committee: *"Give me the age, the fuel type and the ownership type, and I tell you how far cars like this usually have driven; I do not tell you how far this particular car has driven."*

**Why only age, fuel type and ownership.** They are the only pieces of information that the Israeli registry provides *and* that help in the tests. Make and model were tested and **do not help consistently**: in one market they made the result 16% worse, in the other two they improved it by only 1% to 5% (`docs/FINAL_TECHNICAL_REVIEW.md`, section 1). Ownership type (a leased car drives more than a private one) is the only per-vehicle input with an official basis.

**Limitations, in simple words**
1. **It does not hold for an individual car.** The range shown (80%) is wide, roughly as large as the estimate itself, because identical cars drive very different distances. No individual odometer data exist in Israeli open data to prove otherwise.
2. **Performance: equal to a table.** In three countries the calibrated model lands between 0.8% better and 2.4% worse than a simple table "average per age band" (`ml/model1_vs_cbs_results.json`). That is why the system never calls it a measurement.
3. **Data are missing for some cases, and the system warns** ("Low reliability"): electric cars (almost none in the training data), hybrid and gas cars older than 7 years (2 to 5 cars per year of age) and combinations that imply more than 40,000 km per year, more than the CBS publishes for any group. About 7.6% of the vehicles in the sample get the warning (`docs/LIMITATIONS.md`).
4. **The calibration works "on average".** It gets the level of groups right (age × ownership, 3.7% error on the official cells that were not used in the fit), but it does not reduce the uncertainty of a single car.
5. Above 13 years the training data carry no information: the official CBS yearly rates are used.

## Model 2: risk of a defect at the next annual inspection

**What it is.** A ranking: "this car is closer to the end or to the start of the queue of reference cars". It shows three levels (Low, Moderate, High). **It is not a probability**, it is not a breakdown prediction, and it **has not been validated on Israeli cars**. One sentence: *"Compared with hundreds of thousands of inspected British cars, this car sits at a low, medium or high risk position for a defect in the brakes, the electrical system or the engine."*

**Limitations, in simple words**
1. **The target is "a defect found at inspection", not "a breakdown".** It is the closest real, verifiable event that exists in open data.
2. **Data from another country.** Trained on the English inspection data (MOT); independently validated on the Dutch data (RDW). Israeli inspection results are not open.
3. **A good part of the level is the age.** Cars aged 3 to 5 almost always appear as Low (96% for brakes) and cars aged 15 to 20 as High (96%). That is expected: old cars have more defects. The line "compared with cars of the same age" shows what is left beyond age.
4. **How much the model adds beyond age, in numbers** (`docs/MODEL2_VS_AGE_BASELINE.md`), compared with a rule that uses age only, on the same test data:
   * With registry data only, the AUC gain is small: +0.02 to +0.03 in England. In the Netherlands (data new to the model) it is **+0.005 for brakes (practically nothing)**, +0.015 for electrical and +0.019 for engine-related.
   * With the previous inspection result the gain rises to +0.04 to +0.06 (England) and +0.02 to +0.04 (Netherlands). With the measured odometer as well, up to +0.05 to +0.08 (England).
   * Within one age, the AUC is 0.54 to 0.63 (registry only) against 0.50 for the age rule: it separates a little, not a lot. Recall and Precision improve by a few percentage points.
   * **In one honest sentence:** *"The model is a modest improvement over classifying by age alone; the gain is small for brakes without history and larger for the electrical system, for the engine, and when the previous inspection result or the odometer is known."*
5. **It does not cover about 29% of the fleet** (cars under 3 years old, which have not had their first inspection yet; electric; gas; over 20 years old). The system says "no estimate" and explains why, instead of guessing.
6. **A make outside the training data** (about 1% of the covered vehicles) is treated as "other makes", with a warning. The **car model name is not used**: it did not carry over from England to the Netherlands, and only about 50% of Israeli cars have a name that exists in the training data.
7. **Odometer:** the *measured* odometer helps; the Model 1 estimate does **not** feed Model 2 (it did not help in any experiment). This is a difference from the original SRS, recorded as C24.

## System security, in three sentences
Reading is open; writing records requires a **workshop key** (because a stored inspection result is an input of Model 2, and anyone could otherwise change the risk of somebody else's car). The key lives only in `.env` (never in the browser or in git), with a rate limit, a limit on records per car and date validation. It is deliberately simple (no login, as the SRS requires): it proves "an authorised workshop", not *who* wrote the record.

## Hard questions, short answers
* **"So what is machine learning for?"** — It adds a modest improvement over age, larger when an inspection history or an odometer exists, and it is the base for the system to improve when the Ministry opens the Israeli results. The comparison with the age rule is documented, with numbers, which is why the scale is presented as relative.
* **"Why not use age only?"** — It would be almost as good for brakes without history. But the model also uses fuel type, make, history and odometer, and gives the position within the same age; and the scale that is comparable between cars is the same one.
* **"Does this predict breakdowns?"** — No. It predicts a defect found at the annual inspection, as a relative position.
* **"Does it work in Israel?"** — It has not been validated in Israel; the validation was in the Netherlands, a different country from the training one. The system says so on screen.
* **"Is the mileage right?"** — It is an average for similar cars, with a wide range; when there are not enough data the system warns instead of showing a number that looks precise.
* **"Why does the estimated odometer not enter Model 2, as in the SRS?"** — I tested it: it improves nothing (AUC change between −0.001 and +0.002). Forcing the link would be artificial. The *measured* odometer does enter and improves the model.
