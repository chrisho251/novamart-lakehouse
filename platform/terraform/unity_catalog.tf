# -------------------------------------------------------------------------- #
# Managed catalog + medallion schemas — created ALWAYS (works on Free Edition).
# -------------------------------------------------------------------------- #

resource "databricks_catalog" "novamart" {
  name           = var.catalog_name
  comment        = "NovaMart lakehouse — bronze/silver/gold medallion."
  isolation_mode = "ISOLATED"

  # No storage_root => uses the metastore's default managed storage. On paid
  # workspaces you can point this at the external location below instead.
}

resource "databricks_schema" "layers" {
  for_each     = toset(var.schemas)
  catalog_name = databricks_catalog.novamart.name
  name         = each.value
  comment      = "Medallion layer: ${each.value}"
}

# -------------------------------------------------------------------------- #
# External storage — S3-backed storage credential + external location + volume.
# Gated behind enable_external_storage (skip on Free Edition).
# -------------------------------------------------------------------------- #

# Give IAM a moment to propagate before UC validates the credential.
resource "time_sleep" "iam_propagation" {
  count           = var.enable_external_storage ? 1 : 0
  depends_on      = [aws_iam_role_policy.uc_access]
  create_duration = "30s"
}

resource "databricks_storage_credential" "lake" {
  count   = var.enable_external_storage ? 1 : 0
  name    = "${var.prefix}-lake-cred"
  comment = "Access to the NovaMart S3 lake bucket."

  aws_iam_role {
    role_arn = aws_iam_role.uc_access[0].arn
  }

  depends_on = [time_sleep.iam_propagation]
}

resource "databricks_external_location" "lake" {
  count           = var.enable_external_storage ? 1 : 0
  name            = "${var.prefix}-lake"
  url             = "s3://${aws_s3_bucket.lake[0].id}/"
  credential_name = databricks_storage_credential.lake[0].name
  comment         = "Root of the NovaMart lakehouse landing zone."
}

# External volume where the local plane lands raw files (bronze ingestion reads it).
resource "databricks_volume" "landing" {
  count            = var.enable_external_storage ? 1 : 0
  name             = "landing"
  catalog_name     = databricks_catalog.novamart.name
  schema_name      = databricks_schema.layers["bronze"].name
  volume_type      = "EXTERNAL"
  storage_location = "${databricks_external_location.lake[0].url}landing"
  comment          = "Raw file landing zone (parquet/delta from Spark/CDC)."
}
