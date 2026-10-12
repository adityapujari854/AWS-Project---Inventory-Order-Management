"""Response schemas for transparent inventory-advisor insights."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class AdvisorSummary(BaseModel):
    critical: int
    warning: int
    monitor: int
    insufficient_history: int


class InventoryRecommendation(BaseModel):
    product_id: int
    sku: str
    product_name: str
    severity: Literal["critical", "warning", "monitor", "insufficient_history"]
    current_quantity: int
    reorder_threshold: int
    recent_sales_units: int
    recent_depletion_units: int
    suggested_reorder_quantity: int | None
    reason: str


class InventoryAdvisorResponse(BaseModel):
    generated_at: datetime
    analysis_period_days: int
    summary: AdvisorSummary
    recommendations: list[InventoryRecommendation]
    data_note: str
