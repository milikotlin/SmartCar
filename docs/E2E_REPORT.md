# End-to-end test with real Israeli plates

Run: 2026-11-21 against `http://localhost:8000` (live data.gov.il registry and recall services, PostgreSQL, Redis, exported models).

* plates tested: **88** (registry lookups answered: 88); automatic checks: **1995**; failures: **0**
* Model 2 produced an estimate for 52 plates and declined 36 (electric, gas, or age outside 3-20 years, each with its reason)
* security: record writes without / with a wrong workshop key are refused (checked), foreign CORS origin gets no permission
* mileage selection: a typed mileage is user-reported (not a measurement, not stored), the Model 1 estimate is unchanged, invalid values are refused (checked)
* plates with at least one open recall: 1
* latency of `/api/v1/predict` (full request incl. live registry call): median 1.82 s cold, 34 ms with the 24 h cache
* registry outages absorbed by the API's own retry and answered as 503, then retried by the test: 0
* chat endpoint answered from: `deterministic_fallback`

## Sample of results

| plate | make | year | fuel | estimated km (80% range) | Model 2 | recalls |
|---|---|---|---|---|---|---|
| 62886204 | Kia | 2026 | petrol | 45,300 (13,600-80,500) | not covered | 0 |
| 6096279 | Kia | 2012 | petrol | 197,900 (103,000-303,600) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 69307303 | Mazda | 2024 | petrol | 44,600 (13,400-79,300) | not covered | 0 |
| 56320903 | Toyota | 2023 | petrol | 69,600 (20,900-123,700) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 38896104 | Renault | 2025 | petrol | 24,100 (7,200-42,800) | not covered | 0 |
| 30139602 | Chevrolet | 2021 | petrol | 93,100 (45,800-145,900) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 51840301 | Hyundai | 2018 | petrol | 151,900 (84,900-228,900) | covered: brakes moderate, electrical low, engine_emissions low | 0 |
| 7226616 | Mazda | 2005 | petrol | 275,800 (105,800-461,900) | not covered | 0 |
| 70985703 | Hyundai | 2024 | petrol | 46,600 (14,000-82,800) | not covered | 0 |
| 1286163 | Honda | 2007 | petrol | 224,800 (117,000-344,900) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 15742903 | Mitsubishi | 2022 | petrol | 87,000 (42,800-136,300) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 80561701 | Toyota | 2019 | petrol | 149,200 (83,400-224,800) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 5031361 | Mazda | 2007 | petrol | 256,800 (133,600-394,000) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 12710401 | Kia | 2017 | petrol | 156,600 (87,600-236,000) | covered: brakes high, electrical moderate, engine_emissions moderate | 0 |
| 15679802 | Nissan | 2020 | petrol | 115,200 (56,600-180,600) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 64201302 | Seat | 2022 | petrol | 54,600 (26,800-85,500) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 2624130 | Mazda | 2016 | petrol | 175,800 (99,800-251,500) | covered: brakes moderate, electrical moderate, engine_emissions low | 0 |
| 65750804 | Jaecoo | 2026 | petrol | 1,000 (300-1,800) | not covered | 0 |
| 4105511 | Hyundai | 2013 | petrol | 186,200 (105,700-266,400) | covered: brakes high, electrical high, engine_emissions moderate | 0 |
| 80675402 | Chevrolet | 2023 | petrol | 58,900 (17,700-104,800) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 41908101 | Kia | 2018 | petrol | 116,800 (65,300-176,000) | covered: brakes moderate, electrical moderate, engine_emissions low | 0 |
| 6420278 | Hyundai | 2011 | petrol | 210,000 (109,300-322,200) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 8901676 | Skoda | 2012 | petrol | 184,800 (96,100-283,500) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 4543537 | Hyundai | 2016 | petrol | 140,900 (80,000-201,600) | covered: brakes high, electrical high, engine_emissions moderate | 0 |
| 73004302 | Honda | 2023 | petrol | 62,100 (18,600-110,400) | not covered | 0 |
| 8735266 | Toyota | 2009 | petrol | 226,400 (117,800-347,400) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 8735956 | Mazda | 2005 | petrol | 275,800 (105,800-461,900) | not covered | 0 |
| 9144466 | Toyota | 2009 | petrol | 270,300 (140,600-414,600) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 1792268 | Peugeot | 2008 | petrol | 287,900 (149,800-441,700) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 7556912 | Citroen | 2013 | petrol | 186,600 (105,900-266,900) | covered: brakes high, electrical high, engine_emissions high | 0 |
