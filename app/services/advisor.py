"""Transparent, read-only inventory recommendation rules."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.inventory import InventoryMovement, MovementType
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product, ProductStatus
from app.schemas.advisor import AdvisorSummary, InventoryAdvisorResponse, InventoryRecommendation

RECOGNIZED_SALES_STATUSES = (OrderStatus.SHIPPED, OrderStatus.DELIVERED)


def build_inventory_advice(db: Session, days: int) -> InventoryAdvisorResponse:
    """Analyze stored facts only; this function never mutates products, orders, or stock."""
    generated_at = datetime.now(timezone.utc)
    start_date = generated_at - timedelta(days=days)
    active_products = db.scalars(
        select(Product).where(Product.status == ProductStatus.ACTIVE).order_by(Product.quantity, Product.name)
    ).all()

    sales_by_product = dict(
        db.execute(
            select(OrderItem.product_id, func.coalesce(func.sum(OrderItem.quantity), 0))
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.status.in_(RECOGNIZED_SALES_STATUSES), Order.created_at >= start_date)
            .group_by(OrderItem.product_id)
        ).all()
    )
    depletion_by_product = dict(
        db.execute(
            select(InventoryMovement.product_id, func.coalesce(func.sum(-InventoryMovement.quantity_change), 0))
            .where(
                InventoryMovement.movement_type.in_((MovementType.STOCK_OUT, MovementType.ORDER_OUT)),
                InventoryMovement.created_at >= start_date,
            )
            .group_by(InventoryMovement.product_id)
        ).all()
    )
    movement_product_ids = set(
        db.scalars(select(InventoryMovement.product_id).where(InventoryMovement.product_id.in_([p.id for p in active_products]))).all()
    ) if active_products else set()

    recommendations: list[InventoryRecommendation] = []
    counts = {"critical": 0, "warning": 0, "monitor": 0, "insufficient_history": 0}
    for product in active_products:
        recent_sales = int(sales_by_product.get(product.id, 0))
        recent_depletion = int(depletion_by_product.get(product.id, 0))
        threshold = product.reorder_threshold
        near_threshold = product.quantity <= threshold + max(1, threshold // 4)

        if product.quantity == 0:
            severity = "critical"
            suggested = max((recent_sales * 2) - product.quantity, threshold + 1)
            reason = f"Out of stock. {recent_sales} recognized units sold in the last {days} days."
        elif product.quantity <= threshold:
            severity = "warning"
            suggested = max((recent_sales * 2) - product.quantity, threshold + 1 - product.quantity, 1)
            reason = f"Stock ({product.quantity}) is at or below its reorder threshold ({threshold})."
        elif near_threshold and recent_depletion > 0:
            severity = "monitor"
            suggested = None
            reason = f"Stock is near its threshold and {recent_depletion} units were depleted in the last {days} days."
        elif recent_sales == 0 and product.id not in movement_product_ids:
            severity = "insufficient_history"
            suggested = None
            reason = "No sales or inventory-movement history is available for a meaningful recommendation."
        else:
            continue

        if recent_sales == 0 and suggested is not None:
            reason += " No recognized sales history; suggestion uses the configured reorder threshold only."
        counts[severity] += 1
        recommendations.append(
            InventoryRecommendation(
                product_id=product.id,
                sku=product.sku,
                product_name=product.name,
                severity=severity,
                current_quantity=product.quantity,
                reorder_threshold=threshold,
                recent_sales_units=recent_sales,
                recent_depletion_units=recent_depletion,
                suggested_reorder_quantity=suggested,
                reason=reason,
            )
        )

    severity_rank = {"critical": 0, "warning": 1, "monitor": 2, "insufficient_history": 3}
    recommendations.sort(key=lambda item: (severity_rank[item.severity], item.current_quantity, item.product_name))
    return InventoryAdvisorResponse(
        generated_at=generated_at,
        analysis_period_days=days,
        summary=AdvisorSummary(**counts),
        recommendations=recommendations,
        data_note=(
            "Recognized sales use shipped and delivered orders. Trend dates use order creation time; "
            "this is a rule-based operational aid, not a demand forecast."
        ),
    )
