# IAM role that Unity Catalog assumes to read/write the S3 lake bucket.
# Trust policy has two statements:
#   1. the Databricks UC master role assumes it, gated by sts:ExternalId = your
#      Databricks account id;
#   2. the role can assume *itself* — a requirement AWS added for UC credentials.

locals {
  uc_role_name = "${var.prefix}-uc-access"
  uc_role_arn  = var.enable_external_storage ? "arn:aws:iam::${var.aws_account_id}:role/${local.uc_role_name}" : ""
}

data "aws_iam_policy_document" "uc_assume_role" {
  count = var.enable_external_storage ? 1 : 0

  # 1) Databricks UC master role -> this role
  statement {
    sid     = "DatabricksUnityCatalogAssume"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [var.uc_master_role_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.databricks_account_id]
    }
  }

  # 2) self-assumption
  statement {
    sid     = "ExplicitSelfRoleAssumption"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${var.aws_account_id}:root"]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:PrincipalArn"
      values   = [local.uc_role_arn]
    }
  }
}

data "aws_iam_policy_document" "uc_s3_access" {
  count = var.enable_external_storage ? 1 : 0

  statement {
    sid    = "S3DataAccess"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]
    resources = [
      aws_s3_bucket.lake[0].arn,
      "${aws_s3_bucket.lake[0].arn}/*",
    ]
  }

  # Unity Catalog uses STS to generate scoped-down tokens.
  statement {
    sid       = "AllowStsAssume"
    effect    = "Allow"
    actions   = ["sts:AssumeRole"]
    resources = [local.uc_role_arn]
  }
}

resource "aws_iam_role" "uc_access" {
  count              = var.enable_external_storage ? 1 : 0
  name               = local.uc_role_name
  assume_role_policy = data.aws_iam_policy_document.uc_assume_role[0].json
  tags               = { Project = var.prefix }
}

resource "aws_iam_role_policy" "uc_access" {
  count  = var.enable_external_storage ? 1 : 0
  name   = "${var.prefix}-uc-s3-access"
  role   = aws_iam_role.uc_access[0].id
  policy = data.aws_iam_policy_document.uc_s3_access[0].json
}
