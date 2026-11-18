from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InspectionRecord(Base):
    """Result of an annual roadworthiness inspection of a vehicle, by system (the history input of Model 2).

    Deliberately a separate table from maintenance_records: a repair or service is NOT equivalent to an inspection result and the
    model was only validated on inspection results.
    """

    __tablename__ = "inspection_records"
    __table_args__ = (UniqueConstraint("license_plate", "inspection_date", name="uq_inspection_plate_date"),)

    inspection_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    license_plate: Mapped[str] = mapped_column(String(15), ForeignKey("vehicles.license_plate", ondelete="CASCADE"), nullable=False)
    inspection_date: Mapped[date] = mapped_column(Date, nullable=False)
    odometer_km: Mapped[int | None] = mapped_column(Integer)
    brakes_defect: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    electrical_defect: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    engine_defect: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    other_defect: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    vehicle: Mapped["Vehicle"] = relationship(back_populates="inspection_records")
