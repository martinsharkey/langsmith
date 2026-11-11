variable "prism_central_endpoint" {
  description = "Prism Central hostname or IP for the site."
  type        = string
}

variable "cluster_name" {
  description = "Nutanix cluster (Prism Element) that hosts the nodes."
  type        = string
}

variable "subnet_name" {
  description = "Private subnet for the cluster nodes. It must have no default route to the internet (hosting contract)."
  type        = string
}

variable "node_image_name" {
  description = "Hardened, CIS-aligned Linux image for RKE2 nodes, uploaded to Prism Central by the host."
  type        = string
}

variable "ssh_authorized_key" {
  description = "Public key for the break-glass admin account, reachable only from the jump host."
  type        = string
}

variable "mode" {
  description = "b1 (connected) or b2 (disconnected enclave)."
  type        = string
  validation {
    condition     = contains(["b1", "b2"], var.mode)
    error_message = "mode must be b1 or b2."
  }
}

variable "pools" {
  description = "Node pools: count, CPUs, memory, disk and optional GPU passthrough."
  type = map(object({
    count         = number
    vcpus         = number
    memory_mib    = number
    disk_mib      = number
    role          = string # server or agent
    gpu_device_id = optional(number)
  }))
  default = {
    control = { count = 3, vcpus = 8, memory_mib = 32768, disk_mib = 204800, role = "server" }
    general = { count = 3, vcpus = 16, memory_mib = 65536, disk_mib = 307200, role = "agent" }
    storage = { count = 3, vcpus = 16, memory_mib = 65536, disk_mib = 204800, role = "agent" }
  }
}
