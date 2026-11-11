output "nodes" {
  description = "Node names, pools and roles, for the RKE2 install inventory."
  value = {
    for name, vm in nutanix_virtual_machine.node : name => {
      pool = local.nodes[name].pool
      role = local.nodes[name].role
      ip   = try(vm.nic_list_status[0].ip_endpoint_list[0].ip, null)
    }
  }
}
