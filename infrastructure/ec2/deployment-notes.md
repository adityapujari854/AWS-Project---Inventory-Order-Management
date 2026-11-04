# InventoryHub EC2 deployment notes

The EC2 template is a preparation artifact only. It uses the existing VPC `vpc-01ce071104980ab9a`, subnet `subnet-0e209d2de126a7038`, and web security group `sg-01347a74108253023`. It creates one t3.small, one encrypted 20 GiB gp3 root volume, and one temporary public IPv4 address when executed. It creates no VPC, IAM role/profile, RDS, ALB, S3 bucket, certificate, or DNS record.

## Application decision

The current code correctly rejects SQLite in `ENVIRONMENT=production` and requires secure cookies there. Therefore a single EC2/SQLite/HTTP deployment is only a disposable portfolio demonstration using a non-production environment with no real customer data. It is not a safe production configuration for a 3–4 month public service.

For a continuous public deployment, choose one of these before launch:

1. **Portfolio demo:** one instance, SQLite, HTTP only, no real data, single Uvicorn worker, explicit cleanup/backup process. Cheapest, but not production.
2. **Production posture:** RDS MySQL, reviewed migrations, HTTPS with a domain/certificate, secure cookies, then EC2. More cost and a later phase.

Do not change application safeguards to force option 1 to look like option 2.

## Source delivery

The Git remote is GitHub HTTPS, but repository visibility is not known. User data deliberately does not clone code or contain tokens. After connecting through Session Manager, place a reviewed release checkout in a temporary directory and run `sudo infrastructure/ec2/bootstrap.sh <release-directory>`. If the repository is private, use a manually created read-only deploy key or other approved interactive authentication; never place a token/key in CloudFormation, user data, `.env`, or Git.

Before the bootstrap script runs, create `/etc/inventoryhub/inventoryhub.env` manually with permissions `0600`. For a disposable SQLite demonstration, begin from `inventoryhub.env.demo.example`, generate a new session secret, and use the absolute database path `/opt/inventoryhub/data/inventory.db`. Do not copy the local `.env` or SQLite database to EC2. The file must contain only the selected environment’s non-placeholder settings and credentials, entered through a secure manual process.

## S3 review

S3 is optional at startup. The application creates the S3 client only during image operations and reports a safe error when bucket/region configuration is absent. If an approved private bucket is later configured, the EC2 role needs only `s3:GetObject`, `s3:PutObject`, and `s3:DeleteObject` on `arn:aws:s3:::REPLACE_WITH_BUCKET/product-images/*`; it does not need `s3:*`, public access, or access keys.

## Manual Console checkpoint

1. Go to **IAM → Roles → InventoryHub-EC2-SSM-Role → Permissions**. Confirm `AmazonSSMManagedInstanceCore` is attached.
2. Go to **IAM → Roles → InventoryHub-EC2-SSM-Role → Trust relationships**. Confirm principal `ec2.amazonaws.com` is allowed to assume the role.
3. Go to **IAM → Roles → InventoryHub-EC2-SSM-Role → Instance profiles**. Confirm the profile named `InventoryHub-EC2-SSM-Role` exists and contains this role. The CLI user currently lacks `iam:GetInstanceProfile`, so this has not been independently verified.
4. Go to **IAM → Policies → Create policy → JSON**. Review and create the policy in `infrastructure/policies/inventoryhub-ec2-deployment-policy.json` as `InventoryHub-EC2-Deployment`. Attach it to `inventoryhub-cli` only after reviewing the CloudFormation template. Do not edit the existing read-only or VPC policies.
5. Go to **EC2 → Security Groups → sg-01347a74108253023**. Confirm inbound is only TCP 80/443 from the Internet, no TCP 8000, and no SSH. Confirm outbound is only HTTP, HTTPS, and VPC DNS.
6. Go to **Billing and Cost Management**. Confirm current credits, expiry date format, actual budget alert recipients, and Cost Explorer. Use the AWS Pricing Calculator for the final Mumbai quote before approval.

## Cost planning model

The public IPv4 rate is currently published by AWS as $0.005/hour, or about $3.65 for 730 hours. Use the current Mumbai EC2 and gp3 rates from the AWS Pricing Calculator before launch; do not rely on prices from another Region. A conservative planning envelope is **$25–$35/month before tax and unexpected data transfer**, covering one t3.small, 20 GiB gp3, one public IPv4, light traffic, and a small snapshot allowance. That is roughly **$75–$105 for three months** or **$100–$140 for four months**, plus a 30% safety buffer. Credits, Free Tier benefits, taxes, CPU surplus credits, snapshots, and data transfer can change the outcome.

Avoid NAT Gateway, ALB, RDS, Auto Scaling, Elastic IPs, and paid log retention in this Stage A estimate.
