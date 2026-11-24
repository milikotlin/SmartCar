from pydantic import BaseModel


class VehicleProfile(BaseModel):
    license_plate: str
    make: str
    model: str
    manufacture_year: int
    fuel_type: str
    ownership: str
    color: str | None = None
    last_test_date: str | None = None
    # added in the final implementation (all taken from the same registry record)
    license_valid_until: str | None = None      # tokef_dt: the next annual test is due by this date
    first_registration: str | None = None       # moed_aliya_lakvish, "YYYY-M"
    trim_level: str | None = None
    make_raw: str | None = None                 # Hebrew manufacturer string as published
    color_raw: str | None = None                # Hebrew colour as published (shown in the Hebrew interface)
    tozeret_cd: int | None = None               # manufacturer code (joins the official model table: engine size, transmission)
    degem_cd: int | None = None                 # model code
