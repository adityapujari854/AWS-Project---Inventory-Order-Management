"""Safely add the fictional InventoryHub catalogue to a local database."""

from app.database import Base, SessionLocal, engine
from app.models import category, product, supplier  # noqa: F401 - register tables
from app.services.catalogue import seed_sample_catalogue


def main() -> None:
    Base.metadata.create_all(bind=engine)
    database_session = SessionLocal()
    try:
        result = seed_sample_catalogue(database_session)
    finally:
        database_session.close()
    print("Catalogue seed complete:", result)


if __name__ == "__main__":
    main()
