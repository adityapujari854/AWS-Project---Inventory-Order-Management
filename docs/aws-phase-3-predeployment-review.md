# AWS Phase 3: pre-deployment review

This document records the checks completed before VPC provisioning. It is intentionally a **stop point**: do not run the create-stack command until the account, CIDRs, access source, and likely charges have been reviewed and explicitly approved.

## Actual local findings

- Target deployment Region: `ap-south-1` (Mumbai).
- Local AWS configuration currently names `us-east-1` as the default Region. This is not a deployment setting; every review and eventual deployment command must explicitly use `--region ap-south-1` until the default is deliberately changed.
- An AWS credentials file exists locally but was not opened or printed.
- AWS CLI and `cfn-lint` are not installed or available on the command path. Therefore no STS identity check, account-side VPC/AZ lookup, budget/credit lookup, or AWS template validation was performed.
- Existing VPC CIDRs and Availability Zone capacity are unverified. The example `10.42.0.0/16` must not be called conflict-free until the read-only checks below succeed.
- No AWS resource was created, modified, or deleted.

## Template review outcome

The reviewed template is [inventoryhub-stage-a-network.yaml](../infrastructure/cloudformation/inventoryhub-stage-a-network.yaml).

| Item | Review result |
| --- | --- |
| VPC and public subnet | Example `10.42.0.0/16` and `10.42.0.0/24`; account overlap still requires verification. |
| Internet access | Internet Gateway plus the public route table route `0.0.0.0/0`. |
| Public IP | Enabled only for the temporary public subnet so the one Stage A EC2 instance can obtain updates and reach SSM/S3 without NAT. |
| Application access | TCP `8000` requires `ApplicationIngressCidr`; it has no default. Do not use `0.0.0.0/0`. |
| SSH | Disabled by default. If approved as break-glass access, restrict it to the current public IP with `/32` and remove it afterward. |
| Systems Manager | Feasible after attaching an EC2 role with `AmazonSSMManagedInstanceCore` (or a reviewed equivalent). The public subnet and HTTPS egress permit outbound SSM connectivity; the actual role/agent connection is not yet validated. |
| Scope | No EC2, RDS, ALB, NAT Gateway, Route 53, Auto Scaling, S3, or monitoring resource appears in this stack. |

## Cost review before approval

This networking stack contains VPC, subnet, route table, Internet Gateway, and security-group resources. The later EC2 instance, its public IPv4 address, EBS volume/snapshots, data transfer, and any optional log retention are likely Stage A cost drivers. Exact cost cannot be responsibly estimated yet because the instance type, EBS size, uptime, traffic, and account benefits have not been verified in the selected Region.

Before provisioning, use the AWS Pricing Calculator and the account’s Billing, Credits, Free Tier, Cost Explorer, and Budgets pages. Confirm the intended cleanup date and that Budget alerts are already enabled. Alerts notify; they do not guarantee that charges stop.

## Safe PowerShell preflight commands

Install tools only if you choose to do so; installation does not create AWS resources:

```powershell
winget install --exact --id Amazon.AWSCLI
py -m pip install cfn-lint
```

Open a new PowerShell window after AWS CLI installation. These commands are read-only and do not print secret key values:

```powershell
aws --version
aws configure get region
aws sts get-caller-identity --region ap-south-1
cfn-lint infrastructure/cloudformation/inventoryhub-stage-a-network.yaml
aws cloudformation validate-template --region ap-south-1 --template-body file://infrastructure/cloudformation/inventoryhub-stage-a-network.yaml
aws ec2 describe-vpcs --region ap-south-1 --query "Vpcs[].{VpcId:VpcId,Cidr:CidrBlock,Default:IsDefault}" --output table
aws ec2 describe-subnets --region ap-south-1 --query "Subnets[].{SubnetId:SubnetId,VpcId:VpcId,Cidr:CidrBlock,Az:AvailabilityZone}" --output table
aws ec2 describe-availability-zones --region ap-south-1 --filters Name=state,Values=available --query "AvailabilityZones[].ZoneName" --output table
```

Review the identity output, VPC/subnet CIDRs, and available zones. Then check Budgets and Credits manually in the AWS Billing Console. Do not paste credential values into a chat, script, template, repository, or terminal output.

## Parameters requiring your review

| Parameter | Proposed value | Approval needed |
| --- | --- | --- |
| `ProjectName` | `inventoryhub` | Confirm naming/tagging choice. |
| `EnvironmentName` | `stage-a` | Confirm this is temporary. |
| `VpcCidr` | `10.42.0.0/16` | Confirm no overlap after AWS CLI checks. |
| `PublicSubnetCidr` | `10.42.0.0/24` | Confirm it remains within the VPC CIDR. |
| `AvailabilityZone` | `REPLACE_WITH_AVAILABLE_AP_SOUTH_1_AZ` | Choose after the AZ query. |
| `ApplicationIngressCidr` | `REPLACE_WITH_YOUR_CURRENT_PUBLIC_IP/32` | Required. Do not use `0.0.0.0/0`. |
| `ApplicationPort` | `8000` | Temporary direct Uvicorn access only. |
| `EnableSshAccess` | `false` | Keep false; use Session Manager. |
| `AdminSshCidr` | `127.0.0.1/32` | Ignored while SSH is disabled. |

## VPC deployment command — do not run yet

The following is prepared for post-approval use only. It creates billable-account resources and must not be run until the parameters, budget/credit status, and potential charges have been approved:

```powershell
aws cloudformation create-stack `
  --region ap-south-1 `
  --stack-name inventoryhub-stage-a-network `
  --template-body file://infrastructure/cloudformation/inventoryhub-stage-a-network.yaml `
  --parameters `
    ParameterKey=ProjectName,ParameterValue=inventoryhub `
    ParameterKey=EnvironmentName,ParameterValue=stage-a `
    ParameterKey=VpcCidr,ParameterValue=10.42.0.0/16 `
    ParameterKey=PublicSubnetCidr,ParameterValue=10.42.0.0/24 `
    ParameterKey=AvailabilityZone,ParameterValue=REPLACE_WITH_AVAILABLE_AP_SOUTH_1_AZ `
    ParameterKey=ApplicationIngressCidr,ParameterValue=REPLACE_WITH_YOUR_CURRENT_PUBLIC_IP/32 `
    ParameterKey=ApplicationPort,ParameterValue=8000 `
    ParameterKey=EnableSshAccess,ParameterValue=false `
    ParameterKey=AdminSshCidr,ParameterValue=127.0.0.1/32
```

After explicit approval and only after stack creation, wait and inspect it with:

```powershell
aws cloudformation wait stack-create-complete --region ap-south-1 --stack-name inventoryhub-stage-a-network
aws cloudformation describe-stacks --region ap-south-1 --stack-name inventoryhub-stage-a-network --query "Stacks[0].Outputs" --output table
```

The next stage remains VPC provisioning only. It must not create EC2, IAM, RDS, ALB, or any other service in the same action.
