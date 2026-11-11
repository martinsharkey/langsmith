terraform {
  required_version = ">= 1.8.0"
  required_providers {
    nutanix = {
      source  = "nutanix/nutanix"
      version = "= 2.5.0"
    }
  }
}

# Credentials come from the environment (NUTANIX_USERNAME, NUTANIX_PASSWORD), never from files in this repository.
provider "nutanix" {
  endpoint = var.prism_central_endpoint
  port     = 9440
  insecure = false
}
