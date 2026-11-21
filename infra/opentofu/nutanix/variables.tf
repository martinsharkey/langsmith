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
  description = "Public key for the break-glass admin account. Accepted only from jump_host_cidrs."
  type        = string
}

variable "jump_host_cidrs" {
  description = "Addresses of the jump host, in CIDR notation. The break-glass key is accepted only from these (sshd from=)."
  type        = list(string)
  validation {
    condition     = length(var.jump_host_cidrs) > 0 && alltrue([for c in var.jump_host_cidrs : can(cidrhost(c, 0))])
    error_message = "jump_host_cidrs must list at least one address in CIDR notation."
  }
}

variable "control_plane_address" {
  description = "Fixed registration address of the RKE2 servers (DNS name or virtual IP). Joining servers and agents register at https://<address>:9345, and it is added to the servers' tls-san."
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
  # The pool name becomes the node label innovox.uk/pool, and vLLM schedules on innovox.uk/pool=gpu.
  validation {
    condition     = alltrue([for name, cfg in var.pools : cfg.gpu_device_id == null || (name == "gpu" && cfg.role == "agent")])
    error_message = "GPU passthrough is only for agents in the pool named gpu."
  }
  validation {
    condition     = alltrue([for cfg in values(var.pools) : contains(["server", "agent"], cfg.role)])
    error_message = "role must be server or agent."
  }
}
