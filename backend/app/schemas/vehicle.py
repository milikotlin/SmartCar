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
