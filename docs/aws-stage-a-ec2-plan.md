# AWS Phase 2: Stage A EC2 deployment checklist

This checklist is preparation only. Do not launch an instance until the network template, CIDRs, security rules, budget alerts, current pricing, and account credit status have been manually reviewed.

## What Stage A proves

Stage A is a temporary learning deployment: one EC2 instance in a public subnet, serving InventoryHub directly on port 8000. It is not highly available, has no ALB/HTTPS, and is not a suitable place for real customer data. It proves basic Linux deployment, IAM-role S3 access, logging, and `/health` reachability before the later RDS and ALB stages.

## Before launch

1. In the chosen Region, check current Amazon Linux 2023 AMI availability, instance pricing, Free Tier eligibility, and EBS pricing. Select the smallest suitable instance only after that review.
2. Use a small encrypted gp3 EBS root volume, set **Delete on termination** deliberately, and tag the instance/volume with project, environment, owner, and a cleanup date.
3. Apply outputs from the reviewed Stage A networking stack. Set `ApplicationIngressCidr` to a trusted source where possible. Keep SSH disabled and use Session Manager.
4. Create an EC2 instance role and profile. It needs Systems Manager access plus the least-privilege S3 object policy described in [s3-product-images.md](s3-product-images.md). Do not create or paste long-term AWS access keys.
5. Decide how code will be obtained securely: a private Git repository with a deploy key/role, or a reviewed packaged artifact. Do not manually copy secrets into source files.

## Database decision — launch blocker for production

The application deliberately rejects SQLite when `ENVIRONMENT=production`. That is correct for the later RDS design.

For Stage A, SQLite can only be used as a disposable, **single-instance demonstration** with no real customer data, one Uvicorn worker, persistent EBS storage, backups only if consciously configured, and a non-production environment setting. It cannot be shared between instances, is not highly available, and must not be carried forward as the production database.

If the goal is a genuine production-mode deployment, do not launch Stage A with SQLite. Complete the RDS MySQL migration plan first and use the production variables from [aws-deployment-phase-1.md](aws-deployment-phase-1.md).

## Instance setup outline

1. Start Amazon Linux 2023 with the reviewed instance role, subnet, and security group.
2. Use Session Manager to connect. Install the supported Python runtime, Git or the approved artifact retrieval tool, and project dependencies in a Linux virtual environment.
3. Retrieve the application without including `.env`, local SQLite data, or AWS credentials.
4. Put configuration in a root-readable environment file or a later managed secret service. Use placeholders in documentation only. For the direct HTTP demonstration, session cookies cannot be marked `Secure`; restore `SESSION_COOKIE_SECURE=true` when HTTPS is introduced.
5. Create an initial administrator through the documented bootstrap process, then remove bootstrap credentials from the environment file.
6. Create a `systemd` unit that runs Uvicorn as a non-root service account, with `WorkingDirectory`, `EnvironmentFile`, restart-on-failure, and standard-output/error captured by journald.
7. Confirm locally on the instance: `curl http://127.0.0.1:8000/health`. Then confirm access only from the approved source CIDR using the public IP and temporary application port.
8. Review `journalctl` output, application error handling, instance-role S3 image operations (only if a private bucket already exists), and login/logout behavior.

Example service command only; adapt paths and account names on the instance:

```text
/opt/inventoryhub/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## After testing

1. Record the instance ID, security group, public IP, EBS volume, and creation time.
2. Stop the instance when not testing; terminate it and delete unneeded EBS volumes/snapshots after the exercise.
3. Remove temporary direct-ingress and SSH rules, key pairs, test IAM policies, and any unused S3 test objects.
4. Check Cost Explorer and Budgets after usage is recorded. Budget alerts do not guarantee charges stop.
5. Do not advance to multi-instance deployment until RDS, explicit migrations, ALB/HTTPS, and security-group changes have been reviewed.
