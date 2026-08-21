# S3 landing bucket for the lakehouse (raw parquet/delta from the local plane).
# Only created when external storage is enabled.

resource "aws_s3_bucket" "lake" {
  count         = var.enable_external_storage ? 1 : 0
  bucket        = var.lake_bucket_name
  force_destroy = true # portfolio project: allow terraform destroy to clean up

  tags = {
    Project = var.prefix
    Purpose = "lakehouse-landing"
  }
}

resource "aws_s3_bucket_versioning" "lake" {
  count  = var.enable_external_storage ? 1 : 0
  bucket = aws_s3_bucket.lake[0].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lake" {
  count  = var.enable_external_storage ? 1 : 0
  bucket = aws_s3_bucket.lake[0].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "lake" {
  count                   = var.enable_external_storage ? 1 : 0
  bucket                  = aws_s3_bucket.lake[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
