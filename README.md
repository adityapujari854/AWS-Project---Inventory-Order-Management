# InventoryHub — AWS Inventory & Order Management

An inventory and order management platform built locally with FastAPI, then deployed to AWS with EC2, RDS MySQL, S3, an Application Load Balancer, Auto Scaling, CloudWatch/SNS, and CloudFormation.

## Current milestone

Phase 1 — Local application foundation: FastAPI application, environment-based configuration, SQLAlchemy connection layer, starter dashboard, health check, logging, and tests.

## Local setup

1. Create and activate a Python virtual environment.
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and set values as needed.
4. Start the app: `uvicorn app.main:app --reload`
5. Open `http://127.0.0.1:8000` and verify `http://127.0.0.1:8000/health`.

SQLite is the default for the foundation. Set `DATABASE_URL` to a MySQL SQLAlchemy connection URL before the later local-MySQL/RDS steps.

## Planned milestones

1. Product and inventory management
2. Orders and suppliers
3. Dashboard analytics
4. Authentication, S3 image storage, and optional AI advisor
5. AWS network, compute, database, load balancing, monitoring, and CloudFormation
