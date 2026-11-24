# End-to-end test with real Israeli plates

Run: 2026-11-24 against `http://localhost:8000` (live data.gov.il registry and recall services, PostgreSQL, Redis, exported models).

* plates tested: **88** (registry lookups answered: 88); automatic checks: **2004**; failures: **0**
* Model 2 produced an estimate for 52 plates and declined 36 (electric, gas, or age outside 3-20 years, each with its reason)
* security: record writes without / with a wrong workshop key are refused (checked), foreign CORS origin gets no permission
* mileage selection: a typed mileage is user-reported (not a measurement, not stored), the Model 1 estimate is unchanged, invalid values are refused (checked)
* plates with at least one open recall: 1
* latency of `/api/v1/predict` (full request incl. live registry call): median 3.77 s cold, 73 ms with the 24 h cache
* registry outages absorbed by the API's own retry and answered as 503, then retried by the test: 7
* chat endpoint answered from: `deterministic_fallback`

## Sample of results

| plate | make | year | fuel | estimated km (80% range) | Model 2 | recalls |
|---|---|---|---|---|---|---|
| 62886204 | Kia | 2026 | petrol | 10,900 (4,000-18,100) | not covered | 0 |
| 6096279 | Kia | 2012 | petrol | 197,300 (102,400-294,500) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 69307303 | Mazda | 2024 | petrol | 48,700 (18,000-80,500) | not covered | 0 |
| 56320903 | Toyota | 2023 | petrol | 43,000 (15,900-71,200) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 38896104 | Renault | 2025 | petrol | 25,200 (9,300-41,700) | not covered | 0 |
| 30139602 | Chevrolet | 2021 | petrol | 70,100 (30,700-113,300) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 51840301 | Hyundai | 2018 | petrol | 113,700 (52,300-176,900) | covered: brakes moderate, electrical low, engine_emissions low | 0 |
| 7226616 | Mazda | 2005 | petrol | 277,600 (127,700-437,500) | not covered | 0 |
| 70985703 | Hyundai | 2024 | petrol | 27,500 (10,100-45,400) | not covered | 0 |
| 1286163 | Honda | 2007 | petrol | 261,400 (135,700-390,300) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 15742903 | Mitsubishi | 2022 | petrol | 88,300 (38,600-142,800) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 80561701 | Toyota | 2019 | petrol | 101,800 (46,900-158,500) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 5031361 | Mazda | 2007 | petrol | 255,700 (132,700-381,700) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 12710401 | Kia | 2017 | petrol | 127,600 (58,700-198,500) | covered: brakes high, electrical moderate, engine_emissions moderate | 0 |
| 15679802 | Nissan | 2020 | petrol | 84,400 (36,900-136,500) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 64201302 | Seat | 2022 | petrol | 56,800 (24,900-91,900) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 2624130 | Mazda | 2016 | petrol | 143,800 (71,400-218,200) | covered: brakes moderate, electrical moderate, engine_emissions moderate | 0 |
| 65750804 | Jaecoo | 2026 | petrol | 5,400 (2,000-8,900) | not covered | 0 |
| 4105511 | Hyundai | 2013 | petrol | 184,000 (91,400-279,200) | covered: brakes high, electrical high, engine_emissions moderate | 0 |
| 80675402 | Chevrolet | 2023 | petrol | 42,000 (15,500-69,400) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 41908101 | Kia | 2018 | petrol | 112,900 (52,000-175,700) | covered: brakes moderate, electrical moderate, engine_emissions low | 0 |
| 6420278 | Hyundai | 2011 | petrol | 211,500 (109,800-315,700) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 8901676 | Skoda | 2012 | petrol | 197,400 (102,500-294,700) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 4543537 | Hyundai | 2016 | petrol | 143,600 (71,400-217,900) | covered: brakes high, electrical high, engine_emissions moderate | 0 |
| 73004302 | Honda | 2023 | petrol | 41,000 (15,100-67,800) | not covered | 0 |
| 8735266 | Toyota | 2009 | petrol | 234,800 (121,900-350,500) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 8735956 | Mazda | 2005 | petrol | 277,600 (127,700-437,500) | not covered | 0 |
| 9144466 | Toyota | 2009 | petrol | 237,900 (123,500-355,200) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 1792268 | Peugeot | 2008 | petrol | 248,100 (128,800-370,400) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 7556912 | Citroen | 2013 | petrol | 185,700 (92,300-281,800) | covered: brakes high, electrical high, engine_emissions high | 0 |
