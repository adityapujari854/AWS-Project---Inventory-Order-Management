"""Inventory API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.inventory import MovementType


class StockChange(BaseModel):
    quantity: int = Field(gt=0, description="Number of units to add or remove")
    note: str | None = Field(default=None, max_length=255)


class StockAdjustment(BaseModel):
    quantity: int = Field(ge=0, description="New absolute stock quantity")
    note: str | None = Field(default=None, max_length=255)


class InventoryMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    movement_type: MovementType
    quantity_change: int
    quantity_after: int
    note: str | None
    created_at: datetime

