output "dq_dataset_id" {
  description = "BigQuery DQ observability dataset ID"
  value       = google_bigquery_dataset.dq_observability.dataset_id
}

output "cloud_run_url" {
  description = "Cloud Run service URL for the DQ API"
  value       = google_cloud_run_v2_service.dq_api.uri
}

output "service_account_email" {
  description = "DQ Platform service account email"
  value       = google_service_account.dq_platform_sa.email
}

output "anthropic_secret_id" {
  description = "Secret Manager secret ID for Anthropic API key"
  value       = google_secret_manager_secret.anthropic_api_key.secret_id
  sensitive   = true
}
