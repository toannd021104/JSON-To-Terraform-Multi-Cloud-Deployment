terraform {
  required_version = ">= 0.14.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}

# Configure AWS provider
provider "aws" {
  region = var.aws_region  # AWS region (e.g., ap-southeast-1)
}

# Create an EC2 key pair using a public key file
resource "aws_key_pair" "my_key" {
  key_name   = "toanndcloud-keypair"                      # Name of the key pair in AWS
  public_key = file("${path.root}/tf-cloud-init.pub")     # Path to your public SSH key
}
