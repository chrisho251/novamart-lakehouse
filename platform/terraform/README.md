# Terraform — S3 + Unity Catalog

Provisions the lakehouse governance layer as code:

- **Always:** a Unity Catalog `novamart` catalog + medallion schemas
  (`bronze`, `silver`, `gold`, `staging`, `snapshots`) as **managed** storage —
  works on **Databricks Free Edition**.
- **Optional** (`enable_external_storage = true`): an S3 bucket, the IAM role
  Unity Catalog assumes, a **storage credential**, an **external location**, and
  an **external volume** for raw file landing — for paid/full workspaces.

```
versions.tf        providers + version pins (aws, databricks, time)
providers.tf       aws + databricks (workspace-level) providers
variables.tf       inputs + the enable_external_storage flag
s3.tf              lake bucket (versioned, encrypted, private)
iam.tf             UC assume-role (self-assuming) + S3 access policy
unity_catalog.tf   catalog, schemas, storage credential, external loc, volume
grants.tf          catalog + external-location privileges
outputs.tf         catalog / bucket / role / volume path
```

## Free Edition path (managed, no AWS)

```bash
cd platform/terraform
cp terraform.tfvars.example terraform.tfvars    # set catalog_name, admin_principal
export DATABRICKS_HOST="https://dbc-xxxx.cloud.databricks.com"
export DATABRICKS_TOKEN="dapi..."

terraform init
terraform plan      # enable_external_storage=false => catalog + schemas only
terraform apply
```

> ⚠️ Free Edition is serverless-only and typically **cannot create storage
> credentials / external locations**. Keep `enable_external_storage = false`.
> The managed catalog + schemas are all the dbt models and Spark jobs need.

## Full workspace path (S3-backed)

Set in `terraform.tfvars`:

```hcl
enable_external_storage = true
aws_account_id          = "123456789012"
lake_bucket_name        = "novamart-lake-yourname"
databricks_account_id   = "<your databricks account id>"
```

Ensure AWS creds are available (`aws configure` / `AWS_PROFILE`), then
`terraform apply`. UC validates the credential ~30s after the IAM role is
created (handled by a `time_sleep`). If validation races IAM propagation on the
first apply, simply re-run `terraform apply`.

The **external ID** in the IAM trust policy is your Databricks **account id**;
the trust also allows the role to assume **itself** (an AWS requirement for UC
credentials). The UC master-role ARN defaults to the AWS-commercial value and is
overridable via `uc_master_role_arn`.

## Teardown

```bash
terraform destroy
```

Buckets use `force_destroy = true` so destroy cleans them up (portfolio setting;
never do this in production).
