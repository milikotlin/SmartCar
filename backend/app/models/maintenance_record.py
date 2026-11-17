from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"

    record_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    license_plate: Mapped[str] = mapped_column(
        String(15), ForeignKey("vehicles.license_plate", ondelete="CASCADE")
    )
    service_date: Mapped[date] = mapped_column(Date, nullable=False)
    mileage_at_service: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    maintenance_category: Mapped[str | None] = mapped_column(String(50))
    total_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    vehicle: Mapped["Vehicle"] = relationship(back_populates="maintenance_records")
