from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    license_plate: Mapped[str] = mapped_column(String(15), primary_key=True)
    make: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    manufacture_year: Mapped[int] = mapped_column(Integer, nullable=False)
    current_mileage: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    maintenance_records: Mapped[list["MaintenanceRecord"]] = relationship(
        back_populates="vehicle", cascade="all, delete-orphan"
    )
    inspection_records: Mapped[list["InspectionRecord"]] = relationship(
        back_populates="vehicle", cascade="all, delete-orphan"
    )
