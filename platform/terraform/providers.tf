# AWS: provisions the S3 lake bucket + the IAM role Unity Catalog assumes.
provider "aws" {
  region = var.aws_region
}

# Databricks: workspace-level provider (host + PAT). Reads DATABRICKS_HOST /
# DATABRICKS_TOKEN from the environment if the vars are left empty.
provider "databricks" {
  host  = var.databricks_host != "" ? var.databricks_host : null
  token = var.databricks_token != "" ? var.databricks_token : null
}
