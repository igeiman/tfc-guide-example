
locals {
  tfc_hostname     = "app.terraform.io" # For TFE, substitute the custom hostname for your TFE host
  tfc_organization = "irina-geiman"
  component        = reverse(split("/", get_terragrunt_dir()))[0] # This will find the name of the module, such as "01-dynamodb"
  environment = reverse(split("/", get_terragrunt_dir()))[2]
  common_vars = yamldecode(file("vars.yaml"))
}


generate "remote_state" {
  path      = "backend.tf"
  if_exists = "overwrite_terragrunt"
  contents = <<EOF
terraform {
  backend "remote" {
    hostname = "${local.tfc_hostname}"
    organization = "${local.tfc_organization}"
    workspaces {
      # test-tg-environments-dev-us-west-1-01-dynamodb  "${local.environment}-${local.common_vars["Environments"]["${local.environment}"]["Region"]}-${local.component}"
      name = "${basename(get_parent_terragrunt_dir())}-environments-${local.environment}-${local.common_vars["Environments"]["${local.environment}"]["Region"]}-${local.component}"
    }
  }
}
EOF 
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents = <<EOF
provider "aws" {
  region   = "${local.common_vars["Environments"]["${local.environment}"]["Region"]}"
}
EOF
}

terraform {
  extra_arguments "common" {
    commands = get_terraform_commands_that_need_vars()
  }

  # extra_arguments "not-interactive" {
  #   commands = [
  #     "apply",
  #     "destroy"
  #   ]
  #   arguments = [
  #     "-auto-approve",
  #     "-compact-warnings"
  #   ]
  # }
  
  before_hook "print_env" {
    commands     = ["plan", "apply"]
    execute      = ["${find_in_parent_folders("lib")}/debug.sh"]
    run_on_error = true
  }
}

skip = true