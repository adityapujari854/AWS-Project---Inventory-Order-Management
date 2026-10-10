param([string]$Region = "ap-south-1")
$ErrorActionPreference = "Stop"
aws sts get-caller-identity --region $Region
aws cloudformation describe-stacks --region $Region --stack-name inventoryhub-stage-a-network --output table
aws ec2 describe-vpcs --region $Region --vpc-ids vpc-01ce071104980ab9a --output table
aws ec2 describe-subnets --region $Region --subnet-ids subnet-0e209d2de126a7038 --output table
aws ec2 describe-security-groups --region $Region --group-ids sg-01347a74108253023 --output json
aws iam get-instance-profile --instance-profile-name InventoryHub-EC2-SSM-Role --output json
aws iam list-attached-role-policies --role-name InventoryHub-EC2-SSM-Role --output json
aws ssm get-parameter --region $Region --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 --output table
