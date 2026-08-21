variable "prefix" {
  description = "Name prefix for all created resources."
  type        = string
  default     = "novamart"
}

# ---- AWS ------------------------------------------------------------------- #
variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "aws_account_id" {
  description = "Your AWS account id (12 digits). Required when enable_external_storage=true."
  type        = string
  default     = ""
}

variable "lake_bucket_name" {
  description = "S3 bucket for the lakehouse landing zone. Must be globally unique."
  type        = string
  default     = "novamart-lake-change-me"
}

# ---- Databricks ------------------------------------------------------------ #
variable "databricks_host" {
  description = "Workspace URL, e.g. https://dbc-xxxx.cloud.databricks.com. Empty => env DATABRICKS_HOST."
  type        = string
  default     = ""
}

variable "databricks_token" {
  description = "Workspace PAT. Empty => env DATABRICKS_TOKEN."
  type        = string
  default     = ""
  sensitive   = true
}

variable "databricks_account_id" {
  description = "Databricks account id — used as the sts:ExternalId in the IAM trust policy."
  type        = string
  default     = ""
}

variable "catalog_name" {
  type    = string
  default = "novamart"
}

variable "schemas" {
  description = "Schemas (medallion layers) created inside the catalog."
  type        = list(string)
  default     = ["bronze", "silver", "gold", "staging", "snapshots"]
}

variable "admin_principal" {
  description = "Databricks principal (user email or group) granted admin on the catalog."
  type        = string
  default     = "account users"
}

# ---- Feature flags --------------------------------------------------------- #
variable "enable_external_storage" {
  description = <<-EOT
    Create the S3 bucket + IAM role + Unity Catalog storage credential +
    external location + external volume. Set false on Databricks Free Edition
    (serverless-only, no storage-credential creation) — the managed catalog and
    schemas are still created and fully usable.
  EOT
  type        = bool
  default     = false
}

variable "uc_master_role_arn" {
  description = "Databricks Unity Catalog master role that assumes your IAM role (AWS commercial default)."
  type        = string
  default     = "arn:aws:iam::414351767826:role/unity-catalog-prod-UCMasterRole-14S5ZJVKOTYTL"
}
