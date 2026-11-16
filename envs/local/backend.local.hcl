# Backend settings for the local emulator. For a real account keep only
# bucket, key, region, dynamodb_table and encrypt.
bucket                      = "iac-lab-tfstate"
key                         = "envs/local/terraform.tfstate"
region                      = "us-east-1"
dynamodb_table              = "iac-lab-tflock"
encrypt                     = true
use_path_style              = true
skip_credentials_validation = true
skip_metadata_api_check     = true
skip_requesting_account_id  = true
