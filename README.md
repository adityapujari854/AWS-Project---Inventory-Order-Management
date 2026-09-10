# InventoryHub — AWS Inventory & Order Management

An inventory and order management platform built locally with FastAPI, then deployed to AWS with EC2, RDS MySQL, S3, an Application Load Balancer, Auto Scaling, CloudWatch/SNS, and CloudFormation.

## Current milestone

Phase 2 — Product and inventory module: product APIs, stock-in/out/adjustments, low-stock detection, archive protection, and immutable movement history.

## Local setup

1. Create and activate a Python virtual environment.
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and set values as needed.
4. Start the app: `uvicorn app.main:app --reload`
5. Open `http://127.0.0.1:8000` and verify `http://127.0.0.1:8000/health`.

SQLite is the default for the foundation. Set `DATABASE_URL` to a MySQL SQLAlchemy connection URL before the later local-MySQL/RDS steps.

## Planned milestones

1. Orders and suppliers
2. Dashboard analytics
3. Authentication, S3 image storage, and optional AI advisor
4. AWS network, compute, database, load balancing, monitoring, and CloudFormation
