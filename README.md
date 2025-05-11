# Automated Terraform Code Generation Framework

[![AWS](https://img.shields.io/badge/AWS-SSO-orange.svg)](https://aws.amazon.com/single-sign-on/)
[![OpenStack](https://img.shields.io/badge/OpenStack-Terraform-blueviolet.svg)](https://www.openstack.org/)

# Project Setup Guide

This guide will help you set up and run the project, including configuring AWS SSO authentication, running backend services in containers, configuring Terraform with OpenStack, and starting the frontend application.

## Prerequisites

- AWS CLI installed
- Docker and Docker Compose (for backend) and Node.js and npm (for frontend) installed (if you want to use web interface)
- Terraform installed (for infrastructure management)

## AWS SSO Configuration

AWS SSO is used to access resources from containers in this project.

### Step 1: Configure AWS SSO

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

### Step 2: Login to AWS SSO

Authenticate using the configured profile:

```bash
aws sso login --profile my-sso
```

A browser window will open automatically to complete the authentication process.

## Backend Services

### Step 3: Run Backend Services

After successfully logging in to AWS SSO, run the backend services:

```bash
docker compose up --build
```

This command will:
- Build the Docker images if they don't exist
- Create and start containers for all services defined in the docker-compose.yml file
- Display container logs in the terminal

The containers will use your AWS SSO credentials to access the necessary AWS resources.

## Terraform with OpenStack

For infrastructure management with Terraform and OpenStack:

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

3. Use this file when running Terraform commands:
   ```bash
   terraform apply -var-file="your-config.tfvars"
   ```

## Frontend Application

### Step 4: Run Frontend

To run the frontend application:

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm start
   ```

The frontend application will start and connect to the backend services.
