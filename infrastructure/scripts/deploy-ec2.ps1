param(
    [switch]$Execute,
    [string]$Region = "ap-south-1",
    [string]$StackName = "inventoryhub-stage-a-ec2"
)
$ErrorActionPreference = "Stop"
$parameters = @(
    "ParameterKey=ExistingVpcId,ParameterValue=vpc-01ce071104980ab9a",
    "ParameterKey=ExistingPublicSubnetId,ParameterValue=subnet-0e209d2de126a7038",
    "ParameterKey=ExistingApplicationSecurityGroupId,ParameterValue=sg-01347a74108253023",
    "ParameterKey=ExistingInstanceProfileName,ParameterValue=InventoryHub-EC2-SSM-Role"
)
$arguments = @(
    "cloudformation", "create-stack", "--region", $Region, "--stack-name", $StackName,
    "--template-body", "file://infrastructure/cloudformation/inventoryhub-ec2.yaml",
    "--parameters"
) + $parameters + @(
    "--tags", "Key=Project,Value=inventoryhub", "Key=Environment,Value=stage-a", "Key=ManagedBy,Value=cloudformation"
)
Write-Host "Prepared AWS CLI arguments (creates an EC2 instance and EBS volume):" -ForegroundColor Yellow
Write-Host ("aws " + ($arguments -join " "))
if (-not $Execute) { Write-Host "Stopped. Re-run with -Execute only after explicit approval."; exit 0 }
& aws @arguments
