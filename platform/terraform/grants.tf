# Grant the admin principal working privileges on the catalog. On a real team
# you'd split read (analysts) from write (engineers); kept simple here.

resource "databricks_grants" "catalog" {
  catalog = databricks_catalog.novamart.name
  grant {
    principal = var.admin_principal
    privileges = [
      "USE_CATALOG",
      "USE_SCHEMA",
      "CREATE_SCHEMA",
      "SELECT",
      "MODIFY",
      "CREATE_TABLE",
    ]
  }
}

resource "databricks_grants" "external_location" {
  count             = var.enable_external_storage ? 1 : 0
  external_location = databricks_external_location.lake[0].name
  grant {
    principal  = var.admin_principal
    privileges = ["CREATE_EXTERNAL_TABLE", "CREATE_EXTERNAL_VOLUME", "READ_FILES", "WRITE_FILES"]
  }
}
