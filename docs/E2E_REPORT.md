# End-to-end test with real Israeli plates

Run: 2026-11-21 against `http://localhost:8000` (live data.gov.il registry and recall services, PostgreSQL, Redis, exported models).

* plates tested: **88** (registry lookups answered: 88); automatic checks: **1740**; failures: **0**
* Model 2 produced an estimate for 52 plates and declined 36 (electric, gas, or age outside 3-20 years, each with its reason)
* security: record writes without / with a wrong workshop key are refused (checked), foreign CORS origin gets no permission
* mileage selection: a typed mileage is user-reported (not a measurement, not stored), the Model 1 estimate is unchanged, invalid values are refused (checked)
* plates with at least one open recall: 1
* latency of `/api/v1/predict` (full request incl. live registry call): median 0.56 s cold, 16 ms with the 24 h cache
* registry outages absorbed by the API's own retry and answered as 503, then retried by the test: 0
* chat endpoint answered from: `deterministic_fallback`

## Sample of results

| plate | make | year | fuel | estimated km (80% range) | Model 2 | recalls |
|---|---|---|---|---|---|---|
| 62886204 | Kia | 2026 | petrol | 9,100 (0-28,200) | not covered | 0 |
| 6096279 | Kia | 2012 | petrol | 198,200 (91,200-317,200) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 69307303 | Mazda | 2024 | petrol | 60,300 (22,300-111,100) | not covered | 0 |
| 56320903 | Toyota | 2023 | petrol | 52,200 (21,600-90,400) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 38896104 | Renault | 2025 | petrol | 34,800 (10,700-71,900) | not covered | 0 |
| 30139602 | Chevrolet | 2021 | petrol | 83,300 (36,900-132,100) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 51840301 | Hyundai | 2018 | petrol | 124,800 (58,200-197,600) | covered: brakes moderate, electrical low, engine_emissions low | 0 |
| 7226616 | Mazda | 2005 | petrol | 275,900 (123,800-367,600) | not covered | 0 |
| 70985703 | Hyundai | 2024 | petrol | 36,600 (13,500-67,500) | not covered | 0 |
| 1286163 | Honda | 2007 | petrol | 256,800 (112,700-344,500) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 15742903 | Mitsubishi | 2022 | petrol | 106,400 (45,700-173,800) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 80561701 | Toyota | 2019 | petrol | 112,900 (52,700-176,700) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 5031361 | Mazda | 2007 | petrol | 256,800 (112,700-344,500) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 12710401 | Kia | 2017 | petrol | 138,100 (62,500-223,900) | covered: brakes high, electrical moderate, engine_emissions moderate | 0 |
| 15679802 | Nissan | 2020 | petrol | 97,600 (44,500-151,200) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 64201302 | Seat | 2022 | petrol | 68,400 (29,400-111,700) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 2624130 | Mazda | 2016 | petrol | 151,400 (68,000-244,700) | covered: brakes moderate, electrical moderate, engine_emissions low | 0 |
| 65750804 | Jaecoo | 2026 | petrol | 5,200 (0-16,300) | not covered | 0 |
| 4105511 | Hyundai | 2013 | petrol | 186,500 (87,400-297,600) | covered: brakes high, electrical high, engine_emissions moderate | 0 |
| 80675402 | Chevrolet | 2023 | petrol | 52,200 (21,600-90,400) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 41908101 | Kia | 2018 | petrol | 124,800 (58,200-197,600) | covered: brakes moderate, electrical moderate, engine_emissions low | 0 |
| 6420278 | Hyundai | 2011 | petrol | 209,900 (91,300-328,700) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 8901676 | Skoda | 2012 | petrol | 198,200 (91,200-317,200) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 4543537 | Hyundai | 2016 | petrol | 151,400 (68,000-244,700) | covered: brakes high, electrical high, engine_emissions moderate | 0 |
| 73004302 | Honda | 2023 | petrol | 52,200 (21,600-90,400) | not covered | 0 |
| 8735266 | Toyota | 2009 | petrol | 233,400 (105,500-348,900) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 8735956 | Mazda | 2005 | petrol | 275,900 (123,800-367,600) | not covered | 0 |
| 9144466 | Toyota | 2009 | petrol | 233,400 (105,500-348,900) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 1792268 | Peugeot | 2008 | petrol | 245,100 (99,100-335,100) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 7556912 | Citroen | 2013 | petrol | 186,500 (87,400-297,600) | covered: brakes high, electrical high, engine_emissions high | 0 |
