# AWS deployment Phase 1: safety, design, and readiness

This document prepares InventoryHub for an AWS deployment. It does **not** create AWS resources. Use placeholders for account-specific names, IDs, CIDRs, secrets, and database addresses.

## Before using the AWS account

1. Secure the root user with a unique password and MFA. Do not use root for routine work and do not create root access keys.
2. Use an IAM Identity Center user or a named IAM administrator identity for normal administration. Apply least privilege and separate daily work from billing/security administration where possible.
3. In **Billing and Cost Management**, confirm that billing visibility is enabled for the intended administrator. Open **Credits** and **Free Tier** to check the current validity, eligibility, and remaining balance of the approximately $200 credits. Credits and Free Tier benefits are account- and service-specific; neither guarantees that every service is free.
4. Enable Cost Explorer. Create an AWS Budget for actual cost with email alerts at a conservative starting level: 50%, 80%, and 100% of a monthly $10 budget while learning. Treat this as an alerting plan, not a spending cap—Budgets do not automatically stop resources unless a separate automated control is configured and tested.
5. Turn on billing alarms/notifications as allowed by the account configuration, and send alerts to an email address you monitor.
6. Before every deployment, check the current AWS pricing pages and the account’s Free Tier page for the selected Region and instance/database classes.

## Required environment values

Use a secret store or EC2 instance configuration with restricted access; do not commit a `.env` file, AWS keys, passwords, or real identifiers.

```text
ENVIRONMENT=production
DATABASE_URL=mysql+pymysql://inventoryhub_app:replace-with-password@replace-with-rds-endpoint:3306/inventoryhub
SESSION_SECRET=replace-with-a-random-secret-of-at-least-32-characters
SESSION_MAX_AGE_SECONDS=28800
SESSION_COOKIE_SECURE=true
AWS_REGION=replace-with-region
S3_BUCKET_NAME=replace-with-private-bucket-name
S3_PRODUCT_IMAGE_PREFIX=product-images
S3_PRESIGNED_URL_TTL_SECONDS=900
S3_MAX_IMAGE_SIZE_BYTES=5242880
```

On EC2, the AWS SDK uses the attached instance role through its standard credential provider chain. Do not set AWS access keys in this project. The existing S3 guidance and least-privilege object policy are in [s3-product-images.md](s3-product-images.md).

## Production-readiness findings

- The FastAPI app already has structured application logging to standard output, suitable for later CloudWatch log collection.
- `/health` returns a fast, unauthenticated liveness response for a future target group. It does not currently test MySQL or S3 connectivity, so it must not be treated as a full dependency-readiness check.
- Passwords are bcrypt-hashed; sessions are signed, HttpOnly, SameSite cookies backed by server-side database tokens; state-changing APIs require CSRF headers.
- Private S3 uploads use generated object keys, SSE-S3, presigned read URLs, and support an EC2 IAM role.
- Production now refuses SQLite, a placeholder/short session secret, and insecure session cookies. Session cookies must be `Secure` behind ALB HTTPS.
- Local development creates tables and applies a small SQLite-only compatibility update at startup. Production deliberately does not run automatic DDL. Introduce reviewed, versioned migrations (for example, Alembic) and run them once as an explicit deployment step before starting application instances.
- The local default SQLite path is relative to the working directory and is not suitable for multi-instance deployment. RDS MySQL is required before horizontal scaling.
- The first EC2 deployment needs a Linux service definition (for example, systemd) that starts `uvicorn app.main:app --host 0.0.0.0 --port 8000`; it must run with the production variables above and not depend on Windows paths or a local `.venv` location.

## Proposed architecture and traffic flow

```text
Internet
  -> public Application Load Balancer (HTTPS, later stage)
  -> private EC2 application instance(s): FastAPI / Uvicorn
  -> private RDS MySQL

EC2 instance role -> private S3 product-image bucket
CloudWatch <- application/ALB/RDS metrics and logs -> SNS email notifications
```

The ALB is public only when it is introduced. EC2 application instances and RDS remain private. Product-image requests are initiated by the application using the EC2 role; browsers receive only short-lived presigned URLs, not S3 credentials.

### Network outline

- VPC: `replace-with-vpc-cidr`, with at least two Availability Zones reserved for later RDS/ALB expansion.
- Public subnets: ALB, Internet Gateway routes, and only components that genuinely need public ingress.
- Private application subnets: EC2 instances. They have no public IPs in the target architecture.
- Private database subnets: RDS DB subnet group. No public accessibility and no public inbound rule.
- ALB security group: inbound TCP 443 from the Internet once HTTPS exists; optionally TCP 80 only to redirect to HTTPS. Outbound TCP 8000 only to the application security group.
- Application security group: inbound TCP 8000 only from the ALB security group. Outbound TCP 3306 only to the RDS security group and HTTPS 443 as required for AWS APIs/package updates.
- RDS security group: inbound TCP 3306 only from the application security group. No Internet source.
- Administrative access: prefer AWS Systems Manager Session Manager with an instance role. Do not open SSH or RDP to `0.0.0.0/0`.

An initial private-subnet design normally needs NAT for outbound internet access, but a NAT Gateway has ongoing cost. Do not add it without a demonstrated need. Early alternatives are an EC2 instance in a tightly controlled public subnet with no public database, or VPC endpoints for required AWS services; both have security and operational trade-offs to review before use.

## Cost-conscious rollout

### Stage A — one application instance

Create the smallest practical EC2 deployment only after account controls are verified. Use a restrictive security group, instance role, private S3 bucket, and an explicit cleanup date. This is a single-instance deployment, not highly available.

### Stage B — managed database

Add RDS MySQL in private DB subnets, migrate data using a reviewed backup/restore or migration plan, set the MySQL `DATABASE_URL`, and verify application connectivity. RDS instance hours, storage, backups, and Multi-AZ are cost drivers.

### Stage C — load balancing and HTTPS

Add an ALB, target group using `/health`, ACM certificate, and optional Route 53 record once a domain is available. HTTPS terminates at the ALB and secure cookies remain enabled. ALB hours/LCUs, certificates/domain registration, and Route 53 hosted zones can add cost.

### Stage D — availability

Add a second Availability Zone, multiple instances, and Auto Scaling only after the database, session behavior, and health checks are verified. This introduces additional EC2, ALB, data-transfer, and potentially RDS Multi-AZ cost; do not describe Stage A as highly available.

### Stage E — monitoring and recovery

Configure CloudWatch logs, metrics, alarms, SNS notifications, database backups, and restore exercises. Review log-retention and backup-retention settings because retained data is a cost driver.

## Future CloudFormation scope

The later template should parameterize region-appropriate CIDRs, environment name, instance types, key/administrative access strategy, database class and credentials reference, bucket name, alarm email, domain/certificate values, and tags. It should manage the VPC/subnets/routes, security groups, EC2 role/profile, EC2 or launch template, ALB/target group, RDS/subnet group, S3 controls where appropriate, and CloudWatch/SNS resources. Review this design before authoring the stack; do not create a single large stack in Phase 1.

## Cleanup checklist

After each experiment, verify and remove only the resources created for that experiment: EC2 instances and volumes/snapshots, Elastic IPs, ALBs/target groups, RDS instances/snapshots, NAT Gateways, VPC endpoints, S3 test objects/buckets, CloudWatch log groups/retention, alarms, SNS topics/subscriptions, Route 53 records/hosted zones, and CloudFormation stacks. Check Cost Explorer afterwards because charges can appear after usage is recorded.

## Before the first AWS resource

- Confirm MFA, IAM/Identity Center access, billing visibility, actual credit balance, and Budget alerts in the console.
- Choose the Region after comparing current pricing and eligibility.
- Generate a production session secret and decide how it will be stored securely.
- Define resource names, CIDRs, tags, and the Session Manager access model.
- Prepare and test a reviewed MySQL migration plan; do not rely on application startup to create a production schema.
- Recheck the AWS console for existing VPCs, buckets, and billing controls rather than assuming any exist.
