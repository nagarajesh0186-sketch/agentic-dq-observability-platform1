terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  backend "gcs" {
    bucket = "your-terraform-state-bucket"
    prefix = "agentic-dq-platform/terraform"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# BigQuery Dataset for DQ outputs
resource "google_bigquery_dataset" "dq_observability" {
  dataset_id                  = var.dq_dataset_id
  project                     = var.project_id
  location                    = var.bq_location
  description                 = "Agentic DQ Observability Platform output dataset"
  delete_contents_on_destroy  = false

  labels = {
    env     = var.environment
    managed = "terraform"
    purpose = "data-quality"
  }
}

# DQ Results table
resource "google_bigquery_table" "dq_results" {
  dataset_id          = google_bigquery_dataset.dq_observability.dataset_id
  table_id            = "dq_results"
  project             = var.project_id
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "execution_time"
  }

  clustering = ["table_name", "rule_type", "severity"]

  schema = file("${path.module}/schemas/dq_results_schema.json")

  labels = {
    managed = "terraform"
  }
}

# DQ Workflow State table
resource "google_bigquery_table" "dq_workflow_state" {
  dataset_id          = google_bigquery_dataset.dq_observability.dataset_id
  table_id            = "dq_workflow_state"
  project             = var.project_id
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }

  schema = file("${path.module}/schemas/dq_workflow_state_schema.json")
}

# DQ Audit Log table
resource "google_bigquery_table" "dq_audit_log" {
  dataset_id          = google_bigquery_dataset.dq_observability.dataset_id
  table_id            = "dq_audit_log"
  project             = var.project_id
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "timestamp"
  }

  schema = file("${path.module}/schemas/dq_audit_log_schema.json")
}

# Secret Manager secrets
resource "google_secret_manager_secret" "anthropic_api_key" {
  secret_id = "dq-anthropic-api-key"
  project   = var.project_id

  replication {
    auto {}
  }

  labels = {
    managed = "terraform"
    purpose = "dq-platform"
  }
}

resource "google_secret_manager_secret" "slack_webhook_url" {
  secret_id = "dq-slack-webhook-url"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "sendgrid_api_key" {
  secret_id = "dq-sendgrid-api-key"
  project   = var.project_id

  replication {
    auto {}
  }
}

# Service Account for the DQ platform
resource "google_service_account" "dq_platform_sa" {
  account_id   = "dq-platform-sa"
  display_name = "Agentic DQ Platform Service Account"
  project      = var.project_id
}

# IAM bindings for the service account
resource "google_project_iam_member" "dq_bq_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.dq_platform_sa.email}"
}

resource "google_project_iam_member" "dq_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.dq_platform_sa.email}"
}

resource "google_project_iam_member" "dq_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.dq_platform_sa.email}"
}

# Cloud Run service for the API
resource "google_cloud_run_v2_service" "dq_api" {
  name     = "agentic-dq-api"
  location = var.region
  project  = var.project_id

  template {
    service_account = google_service_account.dq_platform_sa.email

    containers {
      image = "gcr.io/${var.project_id}/agentic-dq-api:latest"

      ports {
        container_port = 8000
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "BQ_DQ_DATASET"
        value = var.dq_dataset_id
      }
      env {
        name = "ANTHROPIC_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.anthropic_api_key.secret_id
            version = "latest"
          }
        }
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}
