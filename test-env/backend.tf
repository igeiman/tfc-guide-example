terraform {
  required_version = "~> 0.13"
  backend "remote" {
    hostname     = "app.terraform.io"
    organization = "irina-geiman"
    workspaces {
      name = "test-env"
    }
  }
}