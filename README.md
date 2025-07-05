# Automated Terraform Code Generation Framework
A framework that automatically generates and applies Terraform configurations for AWS and OpenStack based on a simple JSON topology description.

[![AWS](https://img.shields.io/badge/AWS-SSO-orange.svg)](https://aws.amazon.com/single-sign-on/)
[![OpenStack](https://img.shields.io/badge/OpenStack-Terraform-blueviolet.svg)](https://www.openstack.org/)
# Features
- Supports multi-cloud infrastructure: AWS & OpenStack
- Automatically generates `.tf` files based on a JSON topology
- CLI tool for quick deployment
- Web UI (React + FastAPI) for managing environments
- Cloud-init support for bootstrapping VMs
- Bastion host, security groups, floating IP, private/public subnet logic

## CLI Usage 
### Prerequisites

- Python 3 and pip
  
```bash
sudo apt update
sudo apt install python3 python3-pip -y
  ```

- Terraform CLI
```bash
wget https://releases.hashicorp.com/terraform/1.6.6/terraform_1.6.6_linux_amd64.zip
unzip terraform_1.6.6_linux_amd64.zip
sudo mv terraform /usr/local/bin/
  ```
- AWS CLI
```bash
pip install awscli
  ```
- OpenStack CLI
```bash
pip install python-openstackclient
  ``` 
### For infrastructure management with Terraform and OpenStack:

1. Create a `*.tfvars` file containing login information in:
   ```
   /terraform-generator/openstack/
   ```

2. This file should contain information such as:
   ```hcl
    openstack_auth_url     = 
    openstack_region       = 
    openstack_tenant_name  = 
    openstack_user_name    = 
    openstack_password     = 
    external_network_id    = 
   ```

### Using Generator
Create a file named topology.json and place it inside the root folder of the project (terraform-generator/).

Once topology.json is ready, use the following command to generate and deploy infrastructure automatically:
```bash
python3 generate.py [openstack|aws] Number of copy
```

## UI Usage 
### Prerequisites
- Docker and Docker Compose 
[Download Guide](https://docs.docker.com/engine/install/ubuntu/)
- Node.js and npm
[Download Guide](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm)

### AWS SSO Configuration

AWS SSO is used to access resources from containers in this project.

#### Step 1: Configure AWS SSO

Configure AWS SSO with a profile named "my-sso":

```bash
aws configure sso --profile my-sso
```

This will prompt you to enter:
- SSO start URL
- SSO Region
- Default CLI Region
- Default output format
- Permission set

#### Step 2: Login to AWS SSO

Authenticate using the configured profile:

```bash
aws sso login --profile my-sso
```

A browser window will open automatically to complete the authentication process.

### Backend Services

#### Step 3: Run Backend Services

After successfully logging in to AWS SSO, run the backend services:

```bash
docker compose up --build
```

This command will:
- Build the Docker images if they don't exist
- Create and start containers for all services defined in the docker-compose.yml file
- Display container logs in the terminal

The containers will use your AWS SSO credentials to access the necessary AWS resources.




### Frontend Application

#### Step 4: Run Frontend

To run the frontend application:

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Start the development server:
   ```bash
   npm start
   ```

The frontend application will start and connect to the backend services.
