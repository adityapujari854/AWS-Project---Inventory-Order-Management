# AWS Phase 2: Stage A VPC networking

This is the networking design for a temporary, single-instance InventoryHub deployment. It extends [the Phase 1 deployment plan](aws-deployment-phase-1.md) and does not create AWS resources.

## Proposed temporary network

```text
Internet
  -> Internet Gateway
  -> public subnet (10.42.0.0/24)
  -> one EC2 instance running FastAPI on port 8000
```

Example address plan only:

| Resource | Example CIDR | Purpose |
| --- | --- | --- |
| VPC | `10.42.0.0/16` | Isolated project network |
| Public subnet, AZ A | `10.42.0.0/24` | Temporary Stage A EC2 instance |
| Future private app subnet, AZ A | `10.42.10.0/24` | Future ALB-backed application tier |
| Future private app subnet, AZ B | `10.42.11.0/24` | Future second-AZ application tier |
| Future private DB subnet, AZ A | `10.42.20.0/24` | Future RDS subnet group |
| Future private DB subnet, AZ B | `10.42.21.0/24` | Future RDS subnet group |

These ranges have **not** been checked against your AWS account, home network, VPN, or other VPCs. Confirm there is no overlap before creating anything. Choose an Availability Zone that supports the selected instance type; leave capacity decisions until the AWS Console and current regional pricing have been checked.

The VPC enables DNS support and DNS hostnames. The Stage A public subnet assigns public IPv4 addresses automatically so the instance can reach package repositories, Systems Manager, S3, and the Internet Gateway without a NAT Gateway. This lowers initial complexity but makes the instance an Internet-facing asset, so the security group must be narrow.

## Route table

The public route table has one non-local route: `0.0.0.0/0` to the Internet Gateway. The VPC-local route is created by AWS. The route table is associated only with the temporary public subnet.

Later, the ALB will occupy two public subnets. Application instances and RDS will move to private subnets; RDS will have no public route and no public IP. Private applications may need a reviewed outbound strategy—NAT Gateway has ongoing cost, while VPC endpoints or a tightly controlled alternative involve trade-offs.

## Security-group design

| Direction | Rule | Reason |
| --- | --- | --- |
| Inbound | TCP `8000` from `ApplicationIngressCidr` | Temporary direct FastAPI validation only; choose a trusted CIDR where possible. |
| Inbound | TCP `22` from `AdminSshCidr` only when explicitly enabled | Break-glass access only; default is disabled. Never use `0.0.0.0/0`. |
| Outbound | TCP `80`, `443` to Internet | OS/package updates, AWS APIs, SSM, and S3 access. |
| Outbound | TCP/UDP `53` to the VPC CIDR | DNS via the VPC resolver. |

Prefer an EC2 instance role with `AmazonSSMManagedInstanceCore` or an equivalent reviewed policy and use Session Manager for administration. It avoids an exposed SSH port and key-pair handling. If temporary SSH is unavoidable, use your current public IP with `/32`, verify access, then remove the ingress rule and key material after testing.

The later ALB design changes this: the public ALB accepts HTTPS from the Internet, and the application security group accepts only the application port from the ALB security group. HTTPS and an ACM certificate belong to that later ALB stage; Stage A direct HTTP is temporary and should not handle real customer data.

## CloudFormation template

The review-only template is [inventoryhub-stage-a-network.yaml](../infrastructure/cloudformation/inventoryhub-stage-a-network.yaml). It creates only:

- VPC with DNS support and hostnames
- one public subnet
- Internet Gateway, attachment, route table, default route, and association
- one configurable application security group
- optional, restricted SSH ingress, disabled by default

It intentionally creates no EC2, RDS, ALB, NAT Gateway, Route 53, S3, monitoring, or credentials. `ApplicationIngressCidr` has no default so public exposure requires an explicit review decision.

### Validation

`cfn-lint` and the AWS CLI were not available in the local environment during this phase, so no CloudFormation lint or AWS-side validation was claimed.

After installing the tools and before creating a stack, run:

```powershell
python -m pip install cfn-lint
cfn-lint infrastructure/cloudformation/inventoryhub-stage-a-network.yaml
aws cloudformation validate-template --template-body file://infrastructure/cloudformation/inventoryhub-stage-a-network.yaml
```

The first command should report no template errors. The second validates the submitted template with AWS but does not create a stack; it still requires deliberately configured AWS credentials and network access. Review parameters, especially CIDRs and `EnableSshAccess`, before either AWS operation.
