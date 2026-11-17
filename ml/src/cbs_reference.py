"""Official Israeli kilometrage statistics used as a *calibration reference* in Sprint 3.

PRIMARY SOURCES (downloaded and read directly from cbs.gov.il):
  [VKT22] Central Bureau of Statistics, "Vehicle Kilometers Travelled 2022", Publication No. 1923, Jerusalem, Dec 2023.
          https://www.cbs.gov.il/he/publications/doclib/2024/nesua22_1923/e_print.pdf
          Method (p.3): odometer readings recorded at the annual vehicle inspection, whole fleet (administrative files from the Ministry of Transport).
          Table 4 (p.31)  private cars by age; Table 8 (p.35) private cars by ownership / engine cc / first-use period;
          Section 2.2 (p.13) private cars by propulsion; Footnote 4 (p.13): data for electric vehicles NOT publishable yet.
  [REL25] CBS media release 17/09/2025 ("Israel in Figures"), p.34: average annual kilometres travelled by private cars 14,700 km (no change since 2023).
          https://www.cbs.gov.il/he/mediarelease/DocLib/2025/304/11_25_304e.pdf

All averages are thousand km per vehicle per year (a POPULATION MEAN of vehicles of that group, not an individual expectation).
Newer detailed editions (2023/2024) were not located on the CBS site; the 2022 detail is combined with the 2023-24 fleet mean (14.7 vs 15.2).
"""

# (age_from, age_to) in years; CBS 2022 Table 4, private cars
AGE_BANDS = [(0, 3), (4, 6), (7, 9), (10, 13), (14, 19), (20, 29), (30, 99)]
BAND_LABELS = ["0-3", "4-6", "7-9", "10-13", "14-19", "20-29", "30+"]

# avg annual km (thousand), total km (million), vehicles (absolute) — Table 4, p.31
CBS_AGE_2022 = {
    "0-3":   (19.6, 17286, 881923),
    "4-6":   (16.0, 12455, 780053),
    "7-9":   (14.2, 8900, 627158),
    "10-13": (12.6, 7973, 633532),
    "14-19": (11.5, 4993, 432820),
    "20-29": (9.3, 548, 58701),
    "30+":   (4.6, 51, 11121),
}
CBS_AGE_2021 = {"0-3": 19.3, "4-6": 16.2, "7-9": 14.4, "10-13": 12.6, "14-19": 11.2, "20-29": 9.1, "30+": 4.5}
CBS_AGE_2020 = {"0-3": 17.5, "4-6": 13.6, "7-9": 12.2, "10-13": 11.1, "14-19": 10.1, "20-29": 8.7, "30+": 4.9}
CBS_PRIVATE_CAR_TOTAL_2022 = (15.2, 52205, 3425309)

# Table 8, p.35: avg annual km (thousand) of private cars by ownership. keys: first use 2019-2022 / up to 2018 / all
CBS_OWNERSHIP_2022 = {
    "private": {"new": 16.0, "old": 13.4, "all": 13.9},
    "leasing": {"new": 28.4, "old": 26.2, "all": 28.3},
    "company": {"new": 26.5, "old": 22.3, "all": 24.4},   # excluding self-employed
    "rental":  {"new": 26.5, "old": 23.2, "all": 26.1},
    "total":   {"new": 19.6, "old": 13.7, "all": 15.2},
}

# Section 2.2, p.13 — private cars by propulsion (2022). Electric: not published (footnote 4).
CBS_FUEL_2022 = {"gasoline": 14.0, "diesel": 22.8, "hybrid": 21.1, "gas_lpg": 18.8}

# Average annual km of private cars, whole fleet (thousand)
CBS_FLEET_PRIVATE = {2019: 16.2, 2020: 13.5, 2021: 15.3, 2022: 15.2, 2023: 14.7, 2024: 14.7}

# registry -> CBS vocabulary
REGISTRY_OWNERSHIP_TO_CBS = {"private": "private", "dealer": "private", "leasing": "leasing", "company": "company", "rental": "rental"}
REGISTRY_FUEL_TO_CBS = {"petrol": "gasoline", "diesel": "diesel", "hybrid": "hybrid", "lpg_cng": "gas_lpg"}  # electric -> None


def age_to_band(age: int) -> str:
    for (lo, hi), label in zip(AGE_BANDS, BAND_LABELS):
        if lo <= age <= hi:
            return label
    return BAND_LABELS[-1]
