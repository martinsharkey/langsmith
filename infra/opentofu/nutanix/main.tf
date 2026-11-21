data "nutanix_cluster" "site" {
  name = var.cluster_name
}

data "nutanix_subnet" "nodes" {
  subnet_name = var.subnet_name
}

data "nutanix_image" "node" {
  image_name = var.node_image_name
}

locals {
  nodes = merge([
    for pool, cfg in var.pools : {
      for i in range(cfg.count) : "${var.mode}-${pool}-${i + 1}" => merge(cfg, { pool = pool })
    }
  ]...)
  # The first server (by name) starts the cluster; every other node joins through the registration address.
  first_server = sort([for name, node in local.nodes : name if node.role == "server"])[0]
}

resource "nutanix_virtual_machine" "node" {
  for_each = local.nodes

  name                 = each.key
  cluster_uuid         = data.nutanix_cluster.site.id
  num_sockets          = 1
  num_vcpus_per_socket = each.value.vcpus
  memory_size_mib      = each.value.memory_mib

  nic_list {
    subnet_uuid = data.nutanix_subnet.nodes.id
  }

  disk_list {
    data_source_reference = {
      kind = "image"
      uuid = data.nutanix_image.node.id
    }
    disk_size_mib = each.value.disk_mib
  }

  dynamic "gpu_list" {
    for_each = each.value.gpu_device_id == null ? [] : [each.value.gpu_device_id]
    content {
      mode      = "PASSTHROUGH_COMPUTE"
      vendor    = "NVIDIA"
      device_id = gpu_list.value
    }
  }

  guest_customization_cloud_init_user_data = base64encode(templatefile("${path.module}/cloud-init.yaml.tftpl", {
    hostname              = each.key
    pool                  = each.value.pool
    role                  = each.value.role
    first_server          = each.key == local.first_server
    control_plane_address = var.control_plane_address
    ssh_authorized_key    = var.ssh_authorized_key
    jump_host_cidrs       = var.jump_host_cidrs
  }))

  categories {
    name  = "AppType"
    value = "Kubernetes"
  }
}
