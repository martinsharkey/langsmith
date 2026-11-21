# Renders the real cloud-init template through the module (issues #42 and #43). No Prism Central is needed:
# the Nutanix provider is mocked, and only plan-time values are checked. Run with `tofu test`.

mock_provider "nutanix" {}

variables {
  prism_central_endpoint = "prism.cluster.example"
  cluster_name           = "test-cluster"
  subnet_name            = "test-nodes"
  node_image_name        = "test-image"
  ssh_authorized_key     = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKeyOnly breakglass@test"
  jump_host_cidrs        = ["192.0.2.10/32"]
  control_plane_address  = "cp.cluster.example"
  mode                   = "b1"
}

run "break_glass_account_can_use_sudo" {
  command = plan

  # #43: a locked password with a sudo rule that asks for one leaves the account without root.
  assert {
    condition = alltrue(flatten([
      for name, vm in nutanix_virtual_machine.node : [
        for u in yamldecode(base64decode(vm.guest_customization_cloud_init_user_data)).users :
        !try(u.lock_passwd, true) || alltrue([for rule in flatten([u.sudo]) : strcontains(rule, "NOPASSWD:")])
      ]
    ]))
    error_message = "A user with lock_passwd: true has a sudo rule without NOPASSWD."
  }

  # #43: the break-glass key is accepted only from the jump host.
  assert {
    condition = alltrue(flatten([
      for name, vm in nutanix_virtual_machine.node : [
        for u in yamldecode(base64decode(vm.guest_customization_cloud_init_user_data)).users : [
          for k in u.ssh_authorized_keys : startswith(k, "from=\"192.0.2.10/32\" ")
        ]
      ]
    ]))
    error_message = "A break-glass SSH key is not restricted to the jump host addresses."
  }

  # #43: every sudo use by the break-glass account goes to a log file that the audit pipeline ships.
  assert {
    condition = alltrue([
      for name, vm in nutanix_virtual_machine.node :
      anytrue([
        for f in yamldecode(base64decode(vm.guest_customization_cloud_init_user_data)).write_files :
        f.path == "/etc/sudoers.d/90-breakglass-log" && strcontains(f.content, "Defaults:breakglass logfile=")
      ])
    ])
    error_message = "The break-glass sudo log drop-in is missing."
  }
}

run "nodes_join_the_first_server" {
  command = plan

  # #42: exactly one server starts the cluster; every other node joins through the registration address.
  assert {
    condition     = length([for name, vm in nutanix_virtual_machine.node : name if strcontains(base64decode(vm.guest_customization_cloud_init_user_data), "RKE2_FIRST_SERVER=true")]) == 1
    error_message = "Exactly one node must start the cluster."
  }

  assert {
    condition = alltrue([
      for name, vm in nutanix_virtual_machine.node :
      strcontains(base64decode(vm.guest_customization_cloud_init_user_data), "RKE2_FIRST_SERVER=true") ||
      strcontains(base64decode(vm.guest_customization_cloud_init_user_data), "RKE2_SERVER_URL=https://cp.cluster.example:9345")
    ])
    error_message = "A joining node does not get the registration address."
  }
}

run "after_bootstrap_every_node_joins" {
  command = plan

  variables {
    cluster_bootstrapped = true
  }

  # #42: a rebuilt first server must not start a second cluster.
  assert {
    condition = alltrue([
      for name, vm in nutanix_virtual_machine.node :
      strcontains(base64decode(vm.guest_customization_cloud_init_user_data), "RKE2_SERVER_URL=https://cp.cluster.example:9345")
    ])
    error_message = "After bootstrap a node does not join through the registration address."
  }
}

run "gpu_passthrough_only_in_the_gpu_pool" {
  command = plan

  variables {
    pools = {
      control = { count = 3, vcpus = 8, memory_mib = 32768, disk_mib = 204800, role = "server" }
      general = { count = 1, vcpus = 16, memory_mib = 65536, disk_mib = 307200, role = "agent", gpu_device_id = 1 }
    }
  }

  expect_failures = [var.pools]
}
