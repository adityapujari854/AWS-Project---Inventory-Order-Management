param([Parameter(Mandatory=$true)][string]$InstanceId, [string]$Region = "ap-south-1")
$ErrorActionPreference = "Stop"
aws ec2 describe-instances --region $Region --instance-ids $InstanceId --output table
aws ec2 describe-instance-status --region $Region --instance-ids $InstanceId --include-all-instances --output table
aws ssm describe-instance-information --region $Region --filters "Key=InstanceIds,Values=$InstanceId" --output table
