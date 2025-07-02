terraform {
  required_version = ">= 0.14.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_key_pair" "my_key" {
  key_name   = "toanndcloud-keypair"
  public_key = file("${path.root}/tf-cloud-init.pub")
}
