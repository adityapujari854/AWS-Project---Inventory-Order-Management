import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.inventory import InventoryMovement
from app.models.product import Product


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.create_all(bind=engine)
    database_session = SessionLocal()
    database_session.execute(delete(InventoryMovement))
    database_session.execute(delete(Product))
    database_session.commit()
    database_session.close()


def test_health_check_returns_service_status():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "InventoryHub"


def test_dashboard_is_available():
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "InventoryHub" in response.text


def create_product(client: TestClient, **overrides):
    payload = {
        "sku": "WM-001",
        "name": "Wireless Mouse",
        "category": "Accessories",
        "price": "29.99",
        "cost": "12.50",
        "quantity": 10,
        "reorder_threshold": 5,
    }
    payload.update(overrides)
    response = client.post("/api/products", json=payload)
    assert response.status_code == 201
    return response.json()


def test_product_can_be_created_and_listed():
    with TestClient(app) as client:
        created = create_product(client)
        response = client.get("/api/products", params={"search": "mouse"})

    assert created["sku"] == "WM-001"
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["quantity"] == 10


def test_stock_changes_create_a_movement_history():
    with TestClient(app) as client:
        product = create_product(client)
        stock_in = client.post(
            f"/api/products/{product['id']}/inventory/stock-in", json={"quantity": 3, "note": "Supplier delivery"}
        )
        stock_out = client.post(f"/api/products/{product['id']}/inventory/stock-out", json={"quantity": 11})
        history = client.get(f"/api/products/{product['id']}/inventory/movements")

    assert stock_in.json()["quantity"] == 13
    assert stock_out.json()["quantity"] == 2
    assert stock_out.json()["is_low_stock"] is True
    assert [movement["quantity_change"] for movement in history.json()] == [-11, 3]


def test_stock_out_cannot_make_inventory_negative():
    with TestClient(app) as client:
        product = create_product(client, quantity=2)
        response = client.post(f"/api/products/{product['id']}/inventory/stock-out", json={"quantity": 3})

    assert response.status_code == 422
    assert response.json()["detail"] == "Insufficient stock for this operation"


def test_archived_product_is_hidden_and_cannot_change_stock():
    with TestClient(app) as client:
        product = create_product(client)
        archive = client.post(f"/api/products/{product['id']}/archive")
        listing = client.get("/api/products")
        stock_change = client.post(f"/api/products/{product['id']}/inventory/stock-in", json={"quantity": 1})

    assert archive.json()["status"] == "archived"
    assert listing.json()["total"] == 0
    assert stock_change.status_code == 409
