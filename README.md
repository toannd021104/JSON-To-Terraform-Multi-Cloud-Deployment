# Automated Terraform Code Generation Framework
A framework that automatically generates and applies Terraform configurations for AWS and OpenStack based on a simple JSON topology description.

[![AWS](https://img.shields.io/badge/AWS-SSO-orange.svg)](https://aws.amazon.com/single-sign-on/)
[![OpenStack](https://img.shields.io/badge/OpenStack-Terraform-blueviolet.svg)](https://www.openstack.org/)
# Features

- **Supports multi-cloud infrastructure: AWS & OpenStack**
- **Automatically generates `.tf` files based on a JSON topology**
- **Cloud-init support for bootstrapping VMs**
- CLI tool for quick deployment
- Web UI (React + FastAPI) for managing environments
- Bastion host, security groups, floating IP, private/public subnet logic

## Support Resource

### AWS
- **aws_instance**: Tạo máy chủ ảo EC2, bao gồm cả bastion host (điểm truy cập trung gian).
 - **userdata (cloud-init script)**: Script khởi tạo máy ảo tự động khi boot, dùng để cài đặt phần mềm, cấu hình hệ thống ban đầu.
- **aws_vpc**: Vùng mạng ảo riêng cho toàn bộ hạ tầng.
- **aws_subnet**: Các mạng con (public/private) trong VPC.
- **aws_security_group**: Nhóm bảo mật, kiểm soát lưu lượng vào/ra các instance.
- **aws_key_pair**: Cặp khóa SSH để truy cập bảo mật vào EC2.
- **aws_route_table & aws_route_table_association**: Bảng định tuyến và liên kết với subnet.
- **aws_internet_gateway**: Kết nối VPC với internet.
- **aws_nat_gateway**: Cho phép subnet private truy cập internet an toàn.
- **aws_eip**: Địa chỉ IP tĩnh công khai cho các instance cần truy cập từ ngoài.


### OpenStack
- **openstack_compute_instance (Nova)**: Máy chủ ảo, thực hiện tác vụ tính toán, có thể gán floating IP và keypair.
 - **userdata (cloud-init script)**: Script khởi tạo máy ảo tự động khi boot, dùng để cài đặt phần mềm, cấu hình hệ thống ban đầu.
- **openstack_networking_network & openstack_networking_subnet (Neutron)**: Tạo mạng ảo và subnet, phân chia hệ thống thành các vùng mạng độc lập.
- **openstack_networking_router & openstack_networking_router_interface**: Bộ định tuyến ảo, kết nối các subnet và định tuyến lưu lượng ra/vào hệ thống.
- **openstack_networking_floatingip**: Cấp phát và ánh xạ IP công khai cho VM hoặc router, hỗ trợ truy cập từ ngoài.
- **openstack_compute_keypair**: Cặp khóa SSH để xác thực truy cập từ xa vào VM.
- **openstack_networking_secgroup & openstack_networking_secgroup_rule**: Nhóm bảo mật và rule, kiểm soát truy cập dựa trên giao thức, cổng, IP.
### 

## System Architecture

![System Architecture](https://i.postimg.cc/QCmH7LDT/KIentruc.png)
## Workflow

<p align="center">
  <img src="https://i.postimg.cc/fytrtsmH/luonghoatodong.png" alt="Workflow"/>
</p>

## Sample JSON File

Example content of `topology.json`:

```json
{
  "instances": [
    {
      "name": "vm1",
      "image": "ubuntu-jammy",
      "cpu": 2,
      "ram": 4,
      "disk": 20,
      "cloud_init": "cloud-init.yaml",
      "networks": [
        {
          "name": "net1",
          "ip": "192.168.1.10"
        }
      ],
      "keypair": "toanndcloud-keypair",  
      "security_groups": ["default"],
      "floating_ip": true
    }
      ,
    {
      "name": "s2",
      "image": "ubuntu-jammy",
      "cpu": 2,
      "ram": 4,
      "disk": 20,
      "cloud_init": "cloud-init.yaml",
      "networks": [
        {
          "name": "net2",
          "ip": "192.168.2.10"
        }
      ]
    }
  ],
  "networks": [
    {
      "name": "net2",
      "cidr": "192.168.2.0/24",
      "pool": [],
      "gateway_ip": "192.168.2.1",
      "enable_dhcp": true
    },
    {
      "name": "net1",
      "cidr": "192.168.1.0/24",
      "pool": [],
      "gateway_ip": "192.168.1.1",
      "enable_dhcp": true
    },
    {
      "name": "net3",
      "cidr": "192.168.3.0/24",
      "pool": [],
      "gateway_ip": "192.168.3.1",
      "enable_dhcp": true
    }
  ],
  "routers": [
    {
      "name": "R1",
      "networks": [
        {
          "name": "net2",
          "ip": "192.168.2.1"
        },
        {
          "name": "net1",
          "ip": "192.168.1.1"
        },
        {
          "name": "net3",
          "ip": "192.168.3.1"
        }
      ],
      "external": true,
      "routes": []
    }
  ]
}
```

## Result

<p align="center">
  <img src="https://i.postimg.cc/PJTMhkKp/Screenshot-2025-08-22-161416.png" alt="Result"/>
</p>

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
