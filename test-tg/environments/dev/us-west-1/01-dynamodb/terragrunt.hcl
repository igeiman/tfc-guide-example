locals {
  common_vars   = yamldecode(file(find_in_parent_folders("vars.yaml")))
  environment   = reverse(split("/", get_terragrunt_dir()))[2]
  resource      = basename(get_terragrunt_dir())
  resource_vars = local.common_vars["Environments"]["${local.environment}"]["Resources"]["${local.resource}"]
}

terraform {
  source = "git@github.com:ops-guru/tf-aws-clp-iam-user.git?ref=v0.1.0"
}

include {
  path = "${find_in_parent_folders()}"
}

generate "tfvars" {
  path              = "terragrunt.auto.tfvars"
  if_exists         = "overwrite"
  disable_signature = true
  contents          = <<-EOF
users =  ["${local.resource_vars["user"]}"]
EOF
}