# UK MOT extraction: completeness and correctness checks

Source: DVSA anonymised MOT data (Open Government Licence v3.0), yearly files `dft_test_result_<year>.zip` and `dft_test_item_<year>.zip`.
Scope: **all** tests of the year are read; the derived tables keep the class-4 (cars) normal tests of a pseudo-random 1-in-41 subset of **vehicles** (`vehicle_id % 41 == 0`), so each sampled vehicle keeps all its tests and can be followed across years.

## 2022

### Level 1 - integrity of the source streams

| Member | Compression | Bytes decoded | Bytes in zip header | CRC32 decoded | CRC32 in zip header | Verified |
|---|---|---|---|---|---|---|
| test_result_2022.csv | Deflate64 (type 9) | 3,593,668,893 | 3,593,668,893 | 0x22ebd897 | 0x22ebd897 | yes |
| test_item.csv | Deflate (type 8) | 1,912,740,578 | 1,912,740,578 | 0xa2a795b7 | 0xa2a795b7 | yes |

Lines read: results 41,632,878, items 86,352,508. Damaged lines: results 0, items 0.

### Level 2 - derived files

| Check | Result | Detail |
|---|---|---|
| every results line has the expected number of fields and numeric ids | pass |  |
| sampling rule holds for every kept vehicle (vehicle_id % 41 == 0) | pass |  |
| only class-4 normal tests | pass |  |
| no duplicated test_id | pass | (0 duplicates) |
| number of kept tests equals the report | pass | (796,703 vs 796,703) |
| every item row refers to a kept test | pass |  |
| every item line has numeric ids and a known type code | pass | {'A': 1029203, 'F': 483447, 'M': 114594, 'P': 73394} |
| all test dates parse and fall inside the year | pass | (2022-01-01 to 2022-12-31) |
| odometer readings present for the large majority of tests | pass | (0.993) |
| every month of the year is present | pass | {1: 71374, 2: 64997, 3: 84237, 4: 45848, 5: 52283, 6: 57968, 7: 59759, 8: 68242, 9: 81371, 10: 79389, 11: 75773, 12: 55462} |
| share of tests with at least one item row is stable across the year (no collapse in the second half) | pass | (min 0.575, max 0.622) |

Tests kept: 796,703; vehicles: 756,960; item rows: 1,700,638. Tests per month: {1: 71374, 2: 64997, 3: 84237, 4: 45848, 5: 52283, 6: 57968, 7: 59759, 8: 68242, 9: 81371, 10: 79389, 11: 75773, 12: 55462}. Share of tests with items per month: {1: 0.622, 2: 0.601, 3: 0.584, 4: 0.576, 5: 0.575, 6: 0.585, 7: 0.592, 8: 0.597, 9: 0.594, 10: 0.62, 11: 0.622, 12: 0.605}.

## 2023

### Level 1 - integrity of the source streams

| Member | Compression | Bytes decoded | Bytes in zip header | CRC32 decoded | CRC32 in zip header | Verified |
|---|---|---|---|---|---|---|
| test_result.csv | Deflate64 (type 9) | 3,661,104,239 | 3,661,104,239 | 0x3aa6fe30 | 0x3aa6fe30 | yes |
| test_item.csv | Deflate (type 8) | 1,978,006,426 | 1,978,006,426 | 0x842b0136 | 0x842b0136 | yes |

Lines read: results 42,216,721, items 89,302,632. Damaged lines: results 0, items 0.

### Level 2 - derived files

| Check | Result | Detail |
|---|---|---|
| every results line has the expected number of fields and numeric ids | pass |  |
| sampling rule holds for every kept vehicle (vehicle_id % 41 == 0) | pass |  |
| only class-4 normal tests | pass |  |
| no duplicated test_id | pass | (0 duplicates) |
| number of kept tests equals the report | pass | (806,478 vs 806,478) |
| every item row refers to a kept test | pass |  |
| every item line has numeric ids and a known type code | pass | {'A': 1073929, 'F': 490294, 'M': 121620, 'P': 70405} |
| all test dates parse and fall inside the year | pass | (2023-01-01 to 2023-12-31) |
| odometer readings present for the large majority of tests | pass | (0.993) |
| every month of the year is present | pass | {1: 72498, 2: 66936, 3: 83783, 4: 47385, 5: 53778, 6: 63725, 7: 62786, 8: 69365, 9: 80485, 10: 79213, 11: 73664, 12: 52860} |
| share of tests with at least one item row is stable across the year (no collapse in the second half) | pass | (min 0.590, max 0.625) |

Tests kept: 806,478; vehicles: 764,743; item rows: 1,756,248. Tests per month: {1: 72498, 2: 66936, 3: 83783, 4: 47385, 5: 53778, 6: 63725, 7: 62786, 8: 69365, 9: 80485, 10: 79213, 11: 73664, 12: 52860}. Share of tests with items per month: {1: 0.615, 2: 0.605, 3: 0.59, 4: 0.596, 5: 0.59, 6: 0.59, 7: 0.602, 8: 0.606, 9: 0.597, 10: 0.623, 11: 0.625, 12: 0.611}.

## Root cause of the earlier corruption (found and fixed)

Earlier experiments (notebooks 04 to 09, first versions) decoded the *item* files with a Deflate64 decoder. The DVSA item zips are plain Deflate (compression type 8); only the result zips are Deflate64 (type 9). A Deflate64 decoder reads a plain-Deflate length code (258) as a long-match code, so everything after the first such match was garbled without an error. That is why only the first half of each item file looked usable. The decoder is now chosen from the zip header and the integrity of the whole stream is proven by the CRC32 comparison above. The results of the earlier notebooks used only the clean part of the item files, so their conclusions stand, but the second half of the year is now available and the final model was trained on the full years.
