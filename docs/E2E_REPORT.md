# End-to-end test with real Israeli plates

Run: 2026-11-19 against `http://localhost:8000` (live data.gov.il registry and recall services, PostgreSQL, Redis, exported models).

* plates tested: **88** (registry lookups answered: 88); automatic checks: **1570**; failures: **0**
* Model 2 produced an estimate for 52 plates and declined 36 (electric, gas, or age outside 3-20 years, each with its reason)
* plates with at least one open recall: 1
* latency of `/api/v1/predict` (full request incl. live registry call): median 0.52 s cold, 23 ms with the 24 h cache
* registry outages absorbed by the API's own retry and answered as 503, then retried by the test: 0
* chat endpoint answered from: `deterministic_fallback`

## Sample of results

| plate | make | year | fuel | estimated km (80% range) | Model 2 | recalls |
|---|---|---|---|---|---|---|
| 62886204 | Kia | 2026 | petrol | 9,100 (0-28,300) | not covered | 0 |
| 6096279 | Kia | 2012 | petrol | 196,800 (90,600-314,900) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 69307303 | Mazda | 2024 | petrol | 62,900 (22,500-121,800) | not covered | 0 |
| 56320903 | Toyota | 2023 | petrol | 52,900 (21,900-90,500) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 38896104 | Renault | 2025 | petrol | 28,900 (4,900-62,400) | not covered | 0 |
| 30139602 | Chevrolet | 2021 | petrol | 84,300 (36,400-133,800) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 51840301 | Hyundai | 2018 | petrol | 122,100 (57,400-198,600) | covered: brakes moderate, electrical low, engine_emissions low | 0 |
| 7226616 | Mazda | 2005 | petrol | 274,400 (123,100-365,700) | not covered | 0 |
| 70985703 | Hyundai | 2024 | petrol | 38,000 (13,600-73,400) | not covered | 0 |
| 1286163 | Honda | 2007 | petrol | 255,300 (112,000-342,500) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 15742903 | Mitsubishi | 2022 | petrol | 106,600 (46,000-177,500) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 80561701 | Toyota | 2019 | petrol | 121,300 (57,700-187,000) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 5031361 | Mazda | 2007 | petrol | 255,300 (112,000-342,500) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 12710401 | Kia | 2017 | petrol | 136,600 (63,000-220,700) | covered: brakes high, electrical moderate, engine_emissions moderate | 0 |
| 15679802 | Nissan | 2020 | petrol | 97,800 (44,900-152,200) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 64201302 | Seat | 2022 | petrol | 67,300 (29,000-112,000) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 2624130 | Mazda | 2016 | petrol | 151,900 (66,300-252,000) | covered: brakes moderate, electrical moderate, engine_emissions low | 0 |
| 65750804 | Jaecoo | 2026 | petrol | 5,300 (0-16,600) | not covered | 0 |
| 4105511 | Hyundai | 2013 | petrol | 185,000 (86,700-295,300) | covered: brakes high, electrical high, engine_emissions moderate | 0 |
| 80675402 | Chevrolet | 2023 | petrol | 52,900 (21,900-90,500) | covered: brakes low, electrical low, engine_emissions low | 0 |
| 41908101 | Kia | 2018 | petrol | 122,100 (57,400-198,600) | covered: brakes moderate, electrical moderate, engine_emissions low | 0 |
| 6420278 | Hyundai | 2011 | petrol | 208,500 (90,700-326,500) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 8901676 | Skoda | 2012 | petrol | 196,800 (90,600-314,900) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 4543537 | Hyundai | 2016 | petrol | 151,900 (66,300-252,000) | covered: brakes high, electrical high, engine_emissions moderate | 0 |
| 73004302 | Honda | 2023 | petrol | 52,900 (21,900-90,500) | not covered | 0 |
| 8735266 | Toyota | 2009 | petrol | 231,900 (104,900-346,700) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 8735956 | Mazda | 2005 | petrol | 274,400 (123,100-365,700) | not covered | 0 |
| 9144466 | Toyota | 2009 | petrol | 231,900 (104,900-346,700) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 1792268 | Peugeot | 2008 | petrol | 243,600 (98,500-333,100) | covered: brakes high, electrical high, engine_emissions high | 0 |
| 7556912 | Citroen | 2013 | petrol | 185,000 (86,700-295,300) | covered: brakes high, electrical high, engine_emissions high | 0 |
