"""Run the fictional InventoryHub demo-data seed against a local development SQLite database."""

from app.config import get_settings
from app.database import SessionLocal
from app.services.demo_data import seed_demo_data


def main() -> None:
    settings = get_settings()
    if settings.environment.lower() == "production" or not settings.is_sqlite:
        raise SystemExit("Demo data is restricted to a local development SQLite database.")
    with SessionLocal() as db:
        print("Demo seed complete:", seed_demo_data(db))


if __name__ == "__main__":
    main()
