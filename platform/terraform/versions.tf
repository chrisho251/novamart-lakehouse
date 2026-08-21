terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.50"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.11"
    }
  }

  # Recommended for a portfolio: a remote backend so state isn't local-only.
  # backend "s3" {
  #   bucket = "novamart-tfstate"
  #   key    = "unity-catalog/terraform.tfstate"
  #   region = "us-east-1"
  # }
}
