"""Hebrew for every text the pipeline can produce (the only place where these texts are translated).

`TEXTS` is a list of (code, English pattern, Hebrew). A text made of several sentences is consumed pattern by pattern. A text that no pattern covers is returned unchanged, never
guessed; tests/test_i18n.py walks real answers and fails when an English text is left in a Hebrew answer. The codes are language-independent and let the dashboard choose a short label.
"""
import re
from typing import Callable

from app.services.recalls import CATEGORY_EN, RECALL_TYPE_EN
from app.services.translation import MANUFACTURER_TRANSLATIONS

FUEL = {"Petrol": "בנזין", "Diesel": "דיזל", "Electric": "חשמלי", "Hybrid": "היברידי", "Plug-in Hybrid": "היברידי נטען", "LPG/CNG": "גז (גפ״מ)"}
FUEL_KEY = {"petrol": "בנזין", "diesel": "דיזל", "electric": "חשמל", "hybrid": "היברידי", "lpg_cng": "גז (גפ״מ)", "LPG/CNG": "גז (גפ״מ)", "unknown": "לא ידוע"}
OWNERSHIP = {"Private": "פרטי", "Company": "חברה", "Leasing": "ליסינג", "Government": "ממשלתי", "Rental": "השכרה", "Public": "ציבורי", "Cooperative": "אגודה שיתופית", "Dealer": "סוחר"}
LEVEL = {"Low": "נמוך", "Moderate": "בינוני", "High": "גבוה"}
SYSTEM_SHORT = {"brakes": "בלמים", "electrical": "חשמל", "engine-related": "מנוע"}
RULE_LABEL = {
    "oil": "שמן מנוע ומסנן שמן",
    "brakes": "בדיקת מערכת הבלמים (רפידות, דיסקים, צנרת)",
    "brake_fluid": "החלפת נוזל בלמים",
    "tires": "בדיקת צמיגים (סוליה, לחץ, גיל)",
    "coolant": "החלפת נוזל קירור",
    "battery": "בדיקת מצבר 12 וולט",
    "filters": "מסנני אוויר ומזגן",
}
RULE_ADVICE = {
    "oil": "להחליף שמן מנוע ומסנן שמן.",
    "brakes": "לבדוק רפידות, דיסקים, צנרת ומפלס הנוזל.",
    "brake_fluid": "להחליף נוזל בלמים (סופח לחות עם הזמן).",
    "tires": "לבדוק עומק סוליה, לחץ ודפנות.",
    "coolant": "להחליף נוזל קירור לפי ספר הרכב.",
    "battery": "לבדוק את המצבר; מצבר חלש הוא גורם נפוץ לתקלות תאורה וחשמל.",
    "filters": "להחליף מסנני אוויר ומזגן.",
}
RULE_LABEL_EN_LOWER = {
    "engine oil and oil filter": "oil", "brake system inspection (pads, discs, lines)": "brakes", "brake fluid replacement": "brake_fluid", "tyre inspection (tread, pressure, age)": "tires",
    "coolant replacement": "coolant", "12 v battery test": "battery", "air and cabin filters": "filters",
}
RECALL_CATEGORY = {en: he for he, en in CATEGORY_EN.items()}
RECALL_TYPE = {en: he for he, en in RECALL_TYPE_EN.items()}
SITUATION = {"no records (plate only)": "ללא רשומות (מספר רישוי בלבד)", "odometer known": "מד האוץ ידוע", "last inspection known": "תוצאת הטסט האחרון ידועה",
             "odometer + last inspection": "מד האוץ ותוצאת הטסט האחרון ידועים"}
SITUATION_TAG = {"plate only": "מספר רישוי בלבד", "all situations": "כל המצבים"}
PART = {"combustion": "מנוע בעירה", "electric / hybrid": "חשמלי / היברידי"}
MISSING = {"engine size": "נפח המנוע לא נמצא", "transmission": "סוג התיבה לא נמצא", "engine size and transmission": "נפח המנוע וסוג התיבה לא נמצאו"}
VERSUS_AGE = {"lower than most": "נמוך מרוב כלי הרכב", "about typical for": "אופייני לכלי הרכב", "higher than most": "גבוה מרוב כלי הרכב"}

N = r"(\d[\d,]*)"                                   # a whole number, with or without thousands separators


def _rule(english: str) -> str:
    return RULE_LABEL[RULE_LABEL_EN_LOWER[english]] if english in RULE_LABEL_EN_LOWER else english


Hebrew = str | Callable[[re.Match], str]
TEXTS: list[tuple[str, str, Hebrew]] = [
    # ---- Model 1: notes, reliability, label
    ("m1_age_capped", rf"age above {N}: capped", r"גיל מעל \1: הוגבל"),
    ("m1_ownership_unknown", r"ownership not in the official statistics: average factor used", "סוג הבעלות אינו מופיע בסטטיסטיקה הרשמית: נעשה שימוש במקדם הממוצע"),
    ("m1_beyond_data", rf"age above {N}: beyond the training data, official yearly rates continue", r"גיל מעל \1: מעבר לנתוני האימון, החישוב ממשיך לפי הקצב השנתי הרשמי"),
    ("m1_imputed", r"(engine size and transmission|engine size|transmission) not found in the official model data: filled by the KNN imputer \(K=5\) from similar vehicles",
     lambda m: f"{MISSING[m[1]]} בטבלת הדגמים הרשמית: הושלם מכלי רכב דומים (KNN, K=5)"),
    ("m1_no_ev_statistics", r"no official Israeli statistics exist for electric vehicles: the estimate rests on UK electric odometers",
     "אין סטטיסטיקה ישראלית רשמית לרכב חשמלי: האומדן נשען על מדי אוץ של רכב חשמלי בבריטניה"),
    ("m1_unknown_fuel", r"unknown fuel type: the petrol curve is used", "סוג דלק לא ידוע: נעשה שימוש בעקומת הבנזין"),
    ("m1_old_for_fuel", rf"older than {N} years: the real (\w+) vehicles of this age are mostly former taxis, so the official average curve continues",
     lambda m: f"מעל {m[1]} שנים: רוב כלי הרכב מסוג {FUEL_KEY.get(m[2], m[2])} בגיל זה הם מוניות לשעבר, ולכן החישוב ממשיך לפי הממוצע הרשמי"),
    ("m1_too_few", rf"too few real (.+?) vehicles of this age \({N}\) support the estimate",
     lambda m: f"מעט מדי כלי רכב אמיתיים מסוג {FUEL_KEY.get(m[1], m[1])} בגיל זה ({m[2]}) תומכים באומדן"),
    ("m1_official_average", rf"the model implies about {N} km per year, above every official group average: the official average for this age and ownership is shown instead",
     r"המודל מצביע על כ-\1 ק״מ בשנה, מעל כל ממוצע רשמי: מוצג במקומו הממוצע הרשמי לגיל ולבעלות"),
    ("m1_label_reported", rf"User-reported mileage: {N} km, typed by the user for this view; it has not been verified or officially confirmed and is not stored\.",
     r"קילומטראז׳ שהוזן על ידי המשתמש: \1 ק״מ, לתצוגה זו בלבד; לא אומת, לא אושר רשמית ואינו נשמר."),
    ("m1_label_measured", rf"Measured odometer {N} km as of ([\d-]+) \(from a service or inspection record\)\.", r"מד אוץ מדוד: \1 ק״מ נכון ל-\2 (מרשומת טיפול או בדיקה)."),
    ("m1_label_compare", rf"Model 1 estimate for comparison: {N} km \(indicative 80% range {N}-{N}\)\.", r"אומדן מודל 1 להשוואה: \1 ק״מ (טווח אינדיקטיבי של 80%: \2–\3)."),
    ("m1_label_on_file", rf"An odometer of {N} km recorded on ([\d-]+) is on file\.", r"קיימת רשומה של מד אוץ: \1 ק״מ מתאריך \2."),
    ("m1_label_estimate", r"An estimate for similar vehicles, calibrated with official CBS statistics\. The range is indicative \(about 8 in 10 similar vehicles fall inside it\); it is not a measurement and has not been validated for individual Israeli vehicles\.",
     "אומדן לכלי רכב דומים, מכויל לפי נתוני הלמ״ס. הטווח אינדיקטיבי (כ-8 מתוך 10 כלי רכב דומים נמצאים בתוכו); זו אינה מדידה והיא לא תוקפה על כלי רכב בודדים בישראל."),
    ("m1_specs_official", r"official model table \(data\.gov\.il\)", "טבלת הדגמים הרשמית (data.gov.il)"),
    ("m1_specs_partly", r"partly official, partly imputed \(KNN, K=5\)", "חלקית מהטבלה הרשמית, חלקית הושלם (KNN, K=5)"),
    ("m1_specs_imputed", r"imputed \(KNN, K=5\)", "הושלם (KNN, K=5)"),
    # ---- typed mileage: which model used it
    ("km_recorded_wins", r"Used by Model 2 as the mileage\. Not used by the comparison model: it uses the odometer recorded at the last inspection instead, which is the value it was trained on\.",
     "מודל 2 השתמש בערך זה כקילומטראז׳. מודל ההשוואה לא השתמש בו: הוא משתמש במד האוץ שנרשם בטסט האחרון, הערך שעליו אומן."),
    ("km_implausible", rf"Not used by the risk models: {N} km would mean more than {N} km per year for a {N}-year-old vehicle \(Model 2 uses the Model 1 estimate instead\)\. Please check the number\.",
     r"מודלי הסיכון לא השתמשו בערך: \1 ק״מ פירושו יותר מ-\2 ק״מ בשנה לרכב בן \3 שנים (מודל 2 משתמש באומדן של מודל 1). נא לבדוק את המספר."),
    ("km_used", r"Used by Model 2 as the mileage, and by the comparison model as the odometer at the last inspection \(an approximation: it includes the driving since then\)\. Its accuracy depends on what was typed; it is not verified\.",
     "מודל 2 השתמש בערך זה כקילומטראז׳, ומודל ההשוואה השתמש בו כמד האוץ בטסט האחרון (קירוב: הוא כולל את הנסיעה מאז). הדיוק תלוי במה שהוקלד; הערך לא אומת."),
    ("km_not_covered", r"Used by Model 2 as the mileage\. Not used by the comparison model: it does not cover this vehicle\.", "מודל 2 השתמש בערך זה כקילומטראז׳. מודל ההשוואה לא השתמש בו: הוא אינו מכסה רכב זה."),
    # ---- comparison model (UK inspections)
    ("risk_definition", r"Relative risk that the next annual inspection finds a defect in this system, compared with reference vehicles from UK inspection data\. It is not a prediction of a breakdown and it has not been validated on Israeli vehicles\.",
     "סיכון יחסי שבטסט השנתי הבא יימצא ליקוי במערכת זו, בהשוואה לכלי רכב בנתוני הבדיקות של בריטניה. זו אינה תחזית לתקלה והיא לא תוקפה על כלי רכב בישראל."),
    ("risk_disclaimer", r"These indicators are positions in a ranking, not probabilities of failure\. The model was trained on UK inspections and checked on Dutch inspections; no Israeli inspection results are available, so the levels show relative risk against the reference data only\.",
     "המדדים הם מיקום בדירוג ולא הסתברות לתקלה. המודל אומן על בדיקות בבריטניה ונבדק על בדיקות בהולנד; אין תוצאות בדיקה מישראל, ולכן הרמות מציגות סיכון יחסי לנתוני הייחוס בלבד."),
    ("not_covered_fuel", r"fuel type '(\w+)' is not covered: the inspection data used to train the model are petrol, diesel and hybrid cars",
     lambda m: f"סוג הדלק ({FUEL_KEY.get(m[1], m[1])}) אינו מכוסה: נתוני הבדיקות שעליהם אומן המודל הם של רכבי בנזין, דיזל והיברידיים"),
    ("not_covered_young", rf"the vehicle is under {N} years old at its last inspection: its first annual inspection has not taken place yet, and the model learns from vehicles that already had one",
     r"הרכב בן פחות מ-\1 שנים בבדיקה האחרונה: הטסט השנתי הראשון עדיין לא נערך, והמודל לומד מכלי רכב שכבר עברו טסט"),
    ("not_covered_old", rf"the vehicle is more than {N} years old at its last inspection: the training data hold too few vehicles of that age for a reliable estimate",
     r"הרכב בן יותר מ-\1 שנים בבדיקה האחרונה: בנתוני האימון יש מעט מדי כלי רכב בגיל זה לאומדן אמין"),
    ("make_grouped", rf"make '(.+?)' is outside the {N} makes seen in training: grouped with 'other makes' \(less evidence\)", r"היצרן '\1' אינו אחד מ-\2 היצרנים שבנתוני האימון: שויך ל'יצרנים אחרים' (פחות ראיות)"),
    ("system_brakes", r"Brakes", "בלמים"),
    ("system_electrical", r"Electrical \(mostly lighting\)", "חשמל (בעיקר תאורה)"),
    ("system_engine", r"Engine-related \(emissions, fuel, mounts\)", "מנוע (פליטה, דלק, תושבות)"),
    ("system_explanation", rf"(Low|Moderate|High) relative risk: the estimate is higher than about {N} of 100 reference vehicles of all ages\. Among vehicles aged {N} it is (lower than most|about typical for|higher than most) that age group\.",
     lambda m: f"סיכון יחסי {LEVEL[m[1]]}: האומדן גבוה מכ-{m[2]} מתוך 100 כלי רכב בנתוני הייחוס, בכל הגילים. בקרב כלי רכב בני {m[3]} שנים הוא {VERSUS_AGE[m[4]]} בקבוצת גיל זו."),
    ("scale_reference", r"UK MOT inspections \(2022 to 2023\), out-of-sample scores of vehicles aged 3 to 20, petrol, diesel and hybrid",
     "בדיקות MOT בבריטניה (2022 עד 2023), ציונים מחוץ למדגם האימון של כלי רכב בני 3 עד 20, בנזין, דיזל והיברידי"),
    ("scale_rule", rf"Low: the lowest {N}% of reference vehicles; Moderate: the next {N}%; High: the top {N}%", r"נמוך: \1% הנמוכים מכלי הרכב בנתוני הייחוס; בינוני: \2% הבאים; גבוה: \3% העליונים"),
    ("scale_interval", r"Standard interval of 12 months to the next annual inspection for every vehicle", "מרווח אחיד של 12 חודשים עד הטסט השנתי הבא לכל רכב"),
    ("scale_country", r"The same order of risk was found in Dutch inspection data, with different absolute defect rates\. Israeli inspection results are not available\.",
     "אותו סדר סיכון נמצא גם בנתוני הבדיקות בהולנד, עם שיעורי ליקויים שונים. אין תוצאות בדיקה מישראל."),
    # ---- Model 2
    ("failure_definition", r"Model 2 \(Smart_Car_Models\.pdf\): how likely the vehicle is to need a repair \(a defect found at its next annual inspection\), from its age, mileage \(Model 1\), maintenance and failure history, brand and the Dataset 4 failure distribution\. Electric and hybrid vehicles have their own branch \(Dataset 5\)\.",
     "מודל 2 (Smart_Car_Models.pdf): עד כמה סביר שהרכב יזדקק לתיקון (ליקוי שיימצא בטסט השנתי הבא), לפי הגיל, הקילומטראז׳ (מודל 1), היסטוריית הטיפולים והתקלות, היצרן והתפלגות התקלות במאגר 4. לרכב חשמלי והיברידי ענף נפרד (מאגר 5)."),
    ("failure_disclaimer", r"The level is a position among real UK vehicles, not a probability\. Training rows are Kaggle data and synthetic vehicles; the performance figures come only from real inspections \(UK, Netherlands\)\. There are no Israeli inspection results to check it on\.",
     "הרמה היא מיקום בקרב כלי רכב אמיתיים בבריטניה ולא הסתברות. נתוני האימון הם מאגרי Kaggle וכלי רכב סינתטיים; מדדי הביצוע מבוססים רק על בדיקות אמיתיות (בריטניה, הולנד). אין תוצאות בדיקה מישראל לאימות."),
    ("failure_branch_ice", r"combustion vehicles \(Kaggle Datasets 1 and 4 \+ synthetic vehicles from real inspections\)", "רכב עם מנוע בעירה (מאגרי Kaggle מספר 1 ו-4 + כלי רכב סינתטיים מבדיקות אמיתיות)"),
    ("failure_branch_ev", r"electric and hybrid vehicles \(Kaggle Datasets 5 and 1 \+ synthetic vehicles from real inspections\)", "רכב חשמלי והיברידי (מאגרי Kaggle מספר 5 ו-1 + כלי רכב סינתטיים מבדיקות אמיתיות)"),
    ("failure_level_rule", r"Low / Moderate / High: the lowest, middle and highest third of real UK vehicles by the model's score", "נמוך / בינוני / גבוה: השליש הנמוך, האמצעי והגבוה של כלי רכב אמיתיים בבריטניה לפי ציון המודל"),
    ("assumed_days", r"days since the last maintenance", "ימים מאז הטיפול האחרון"),
    ("assumed_inspection", r"result of the last inspection", "תוצאת הטסט האחרון"),
    ("assumed_odometer", r"true odometer \(Model 1 estimate used\)", "מד האוץ האמיתי (נעשה שימוש באומדן מודל 1)"),
    ("assumed_service_km", r"km since the last service", "ק״מ מאז הטיפול האחרון"),
    ("quality_auc", r"On real UK vehicles in the same situation \((no records \(plate only\)|odometer known|last inspection known|odometer \+ last inspection)\) the model reaches ROC-AUC ([\d.]+) \(0\.5 = chance\); flagging the riskiest (\d+)% finds (\d+)% of the vehicles with a defect\.",
     lambda m: f"על כלי רכב אמיתיים בבריטניה באותו מצב ({SITUATION[m[1]]}) המודל מגיע ל-ROC-AUC של {m[2]} (0.5 = ניחוש); סימון {m[3]}% המסוכנים ביותר מאתר {m[4]}% מכלי הרכב עם ליקוי."),
    ("quality_age", r"This vehicle is outside the ages of the real data \((\d+)-(\d+) years\), so the level is an extrapolation\.", r"גיל הרכב מחוץ לטווח הנתונים האמיתיים (\1–\2 שנים), ולכן הרמה היא אקסטרפולציה."),
    ("quality_ev", r"This branch learned mostly from hybrids: few real electric vehicles have inspection results\.", "ענף זה למד בעיקר מרכב היברידי: למעט כלי רכב חשמליים יש תוצאות בדיקה."),
    ("cmp_model", r"Model 2, (combustion|electric / hybrid)", lambda m: f"מודל 2, {PART[m[1]]}"),
    ("cmp_previous", r"Previous Model 2, (combustion|electric / hybrid)", lambda m: f"מודל 2 הקודם, {PART[m[1]]}"),
    ("cmp_age", r"Age only \(baseline\), (combustion|electric / hybrid)", lambda m: f"גיל בלבד (בסיס השוואה), {PART[m[1]]}"),
    ("cmp_uk", r"Comparison model \(UK inspections\), (brakes|electrical|engine-related)", lambda m: f"מודל השוואה (בדיקות בבריטניה), {SYSTEM_SHORT[m[1]]}"),
    ("cmp_data_dutch", r"real Dutch inspections \(plate only\)", "בדיקות אמיתיות בהולנד (מספר רישוי בלבד)"),
    ("cmp_data_mot", r"real UK MOT inspections", "בדיקות MOT אמיתיות בבריטניה"),
    ("cmp_data_uk_tag", r"real UK inspections \((plate only|all situations)\)", lambda m: f"בדיקות אמיתיות בבריטניה ({SITUATION_TAG[m[1]]})"),
    ("cmp_data_uk", r"real UK inspections", "בדיקות אמיתיות בבריטניה"),
    ("cmp_test_uk", rf"{N} real UK vehicles, defect at the next inspection", r"\1 כלי רכב אמיתיים בבריטניה, ליקוי בטסט הבא"),
    ("cmp_test_oos", r"out of sample, defect at the next inspection", "מחוץ למדגם האימון, ליקוי בטסט הבא"),
    ("cmp_test_nl", r"second country, never used in training", "מדינה שנייה, לא שימשה לאימון"),
    # ---- maintenance rules
    ("rules_disclaimer", r"Generic service intervals, not specific to this make and model and not learned from data; the owner's manual prevails\.",
     "מרווחי טיפול כלליים, שאינם ספציפיים ליצרן ולדגם ואינם נלמדים מנתונים; ספר הרכב קובע."),
    ("odo_reported", r"user-reported \(not verified\)", "דיווח המשתמש (לא מאומת)"),
    ("odo_measured", r"measured", "מדוד"),
    ("odo_estimated", r"estimated \(range shown above\)", "אומדן (הטווח מוצג למעלה)"),
    ("interval_both", rf"{N} months or {N} km", r"\1 חודשים או \2 ק״מ"),
    ("interval_months", rf"{N} months", r"\1 חודשים"),
    ("basis_measured", r"time and measured odometer", "זמן ומד אוץ מדוד"),
    ("basis_estimated", r"time and estimated odometer", "זמן ומד אוץ משוער"),
    ("basis_time", r"time only", "זמן בלבד"),
    ("basis_no_record_km", rf"measured odometer {N} km with no (.+) on record", lambda m: f"מד אוץ מדוד {m[1]} ק״מ, ואין ברשומות: {_rule(m[2])}"),
    ("basis_no_record_age", rf"vehicle is {N} years old; no (.+) on record", lambda m: f"הרכב בן {m[1]} שנים; אין ברשומות: {_rule(m[2])}"),
    # ---- recalls, history, provenance
    ("recall_source", r"Israel Ministry of Transport open data: vehicles with open recalls", "נתונים פתוחים של משרד התחבורה: כלי רכב עם קריאות ריקול פתוחות"),
    ("recall_unavailable", r"recall service unavailable \((\w+)\)", r"שירות הריקול אינו זמין (\1)"),
    ("history_mismatch", r"the latest recorded inspection \(([\d-]+)\) is not the last annual test of the registry \(([\d-]+)\): history variant not used",
     r"הבדיקה האחרונה שנרשמה (\1) אינה הטסט השנתי האחרון במאגר (\2): לא נעשה שימוש בהיסטוריה"),
    ("history_mismatch_plain", r"the latest recorded inspection \(([\d-]+)\) is not the last annual test: history variant not used", r"הבדיקה האחרונה שנרשמה (\1) אינה הטסט השנתי האחרון: לא נעשה שימוש בהיסטוריה"),
    ("history_down", r"history store unavailable \((\w+)\)", r"מאגר ההיסטוריה אינו זמין (\1)"),
    ("model2_down", r"failure-risk model unavailable \((\w+)\)", r"מודל הסיכון אינו זמין (\1)"),
    ("prov_m1", r"Model 1 \(Smart_Car_Models\.pdf\): XGBoost chosen by RMSE/MAE among Linear, Ridge, Random Forest and XGBoost on Kaggle Datasets 7, 8 and 3 plus synthetic vehicles \(from real UK odometers\), tested on real odometers, calibrated to CBS Publication 1923\.",
     "מודל 1 (Smart_Car_Models.pdf): XGBoost נבחר לפי RMSE/MAE מבין Linear, Ridge, Random Forest ו-XGBoost, על מאגרי Kaggle מספר 7, 8 ו-3 וכלי רכב סינתטיים (ממדי אוץ אמיתיים בבריטניה), נבדק על מדי אוץ אמיתיים וכויל לפי פרסום 1923 של הלמ״ס."),
    ("prov_m2", r"Model 2 \(Smart_Car_Models\.pdf\): Kaggle Datasets 1, 4 and 5 plus synthetic vehicles \(from real UK inspections\), tested on real UK and Dutch inspections; not validated on Israeli vehicles\.",
     "מודל 2 (Smart_Car_Models.pdf): מאגרי Kaggle מספר 1, 4 ו-5 וכלי רכב סינתטיים (מבדיקות אמיתיות בבריטניה), נבדק על בדיקות אמיתיות בבריטניה ובהולנד; לא תוקף על כלי רכב בישראל."),
    ("prov_uk", r"Comparison model: XGBoost trained on UK MOT inspections, validated on Dutch RDW inspections; not validated on Israeli vehicles\.",
     "מודל ההשוואה: XGBoost שאומן על בדיקות MOT בבריטניה ותוקף על בדיקות RDW בהולנד; לא תוקף על כלי רכב בישראל."),
    ("prov_rules", r"Maintenance advice comes from generic rules; recalls come from the Ministry of Transport open data\.", "המלצות הטיפול מבוססות על כללים כלליים; הריקולים מהנתונים הפתוחים של משרד התחבורה."),
]
_COMPILED = [(code, re.compile(en), he) for code, en, he in TEXTS]


def _match(text: str, pos: int) -> tuple[str, str, int] | None:
    """Longest pattern that matches at `pos` and ends at the end of the text or before a space: (code, Hebrew, end)."""
    best = None
    for code, rx, he in _COMPILED:
        m = rx.match(text, pos)
        if m and (m.end() == len(text) or text[m.end()] == " ") and (best is None or m.end() > best[2]):
            best = (code, he(m) if callable(he) else m.expand(he), m.end())
    return best


def parts(text: str | None) -> list[tuple[str, str]] | None:
    """[(code, Hebrew), ...] for a text made only of known sentences; None when any part of it is unknown."""
    if not text:
        return None
    out, pos = [], 0
    while pos < len(text):
        hit = _match(text, pos)
        if hit is None:
            return None
        out.append((hit[0], hit[1]))
        pos = hit[2] + 1                                # the space between two sentences
    return out


def he(text: str | None) -> str | None:
    """Hebrew text, or the text unchanged when it is not a known one (free text, a name, a date)."""
    p = parts(text)
    return text if p is None else " ".join(h for _, h in p)


def code(text: str | None) -> str | None:
    """Language-independent identifier of a pipeline text (the first sentence's)."""
    p = parts(text)
    return p[0][0] if p else None


# ---------------------------------------------------------------- registry values
_MAKES_BY_LENGTH = sorted(MANUFACTURER_TRANSLATIONS, key=len, reverse=True)


def make_he(make: str, make_raw: str | None) -> str:
    """The brand as the registry publishes it in Hebrew (the registry value also carries the country of manufacture)."""
    s = re.sub(r"\s+", " ", (make_raw or "").replace('"', "").strip())
    return next((p for p in _MAKES_BY_LENGTH if s.startswith(p)), s or make)
