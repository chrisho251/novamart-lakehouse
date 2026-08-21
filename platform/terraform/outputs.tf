output "catalog_name" {
  description = "Unity Catalog created for the lakehouse."
  value       = databricks_catalog.novamart.name
}

output "schemas" {
  description = "Medallion schemas created inside the catalog."
  value       = [for s in databricks_schema.layers : s.name]
}

output "lake_bucket" {
  description = "S3 lake bucket (null when external storage disabled)."
  value       = var.enable_external_storage ? aws_s3_bucket.lake[0].id : null
}

output "uc_iam_role_arn" {
  description = "IAM role assumed by Unity Catalog (null when disabled)."
  value       = var.enable_external_storage ? aws_iam_role.uc_access[0].arn : null
}

output "external_location_url" {
  description = "s3:// root registered as a UC external location (null when disabled)."
  value       = var.enable_external_storage ? databricks_external_location.lake[0].url : null
}

output "landing_volume_path" {
  description = "UC volume path the local plane lands raw files into."
  value       = var.enable_external_storage ? "/Volumes/${var.catalog_name}/bronze/landing" : null
}
