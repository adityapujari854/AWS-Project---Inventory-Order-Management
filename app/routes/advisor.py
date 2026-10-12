"""Authenticated read-only Inventory Advisor endpoint."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.advisor import InventoryAdvisorResponse
from app.security import require_admin, verify_csrf
from app.services.advisor import build_inventory_advice

router = APIRouter(prefix="/api/advisor", tags=["inventory advisor"], dependencies=[Depends(require_admin), Depends(verify_csrf)])


@router.get("", response_model=InventoryAdvisorResponse)
def inventory_advisor(
    days: int = Query(default=30, ge=1, le=365), db: Session = Depends(get_db)
) -> InventoryAdvisorResponse:
    if not 1 <= days <= 365:
        raise HTTPException(status_code=422, detail="days must be between 1 and 365")
    return build_inventory_advice(db, days)
