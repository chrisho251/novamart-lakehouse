# AWS: provisions the S3 lake bucket + the IAM role Unity Catalog assumes.
# On the Free Edition path (enable_external_storage=false) every aws_* resource
# has count=0, so no real AWS API call ever happens — but Terraform still
# configures the "aws" provider block up front, before it knows any count is 0.
# Without real AWS credentials that configure step fails ("No valid credential
# sources found") and even tries to probe the EC2 metadata endpoint. Skipping
# validation and using placeholder credentials avoids all of that when external
# storage is disabled; when it's enabled, normal credential resolution applies.
provider "aws" {
  region = var.aws_region

  access_key = var.enable_external_storage ? null : "unused"
  secret_key = var.enable_external_storage ? null : "unused"

  skip_credentials_validation = !var.enable_external_storage
  skip_requesting_account_id  = !var.enable_external_storage
  skip_region_validation      = !var.enable_external_storage
  skip_metadata_api_check     = !var.enable_external_storage
}

# Databricks: workspace-level provider (host + PAT). Reads DATABRICKS_HOST /
# DATABRICKS_TOKEN from the environment if the vars are left empty.
provider "databricks" {
  host  = var.databricks_host != "" ? var.databricks_host : null
  token = var.databricks_token != "" ? var.databricks_token : null
}
