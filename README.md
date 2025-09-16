# 🌩️ JSON-To-Terraform Multi-Cloud Deployment

> 🚀 A framework that automatically **generates and deploys Terraform configurations** on **AWS** and **OpenStack** from a single **JSON topology file**, with built-in **Cloud-Init**, **CLI**, and **Web UI (React + FastAPI)**.

[![AWS](https://img.shields.io/badge/AWS-Supported-orange.svg)](https://aws.amazon.com/)
[![OpenStack](https://img.shields.io/badge/OpenStack-Supported-blueviolet.svg)](https://www.openstack.org/)
[![Terraform](https://img.shields.io/badge/Terraform-Automated-success.svg)](https://www.terraform.io/)

---

### 🧩 Situation
In multi-cloud environments, engineers often need to provision the **same infrastructure on both AWS and OpenStack**.  
Manually writing `.tf` files is slow, error-prone, and hard to reuse when deploying multiple environments.

---

### 🎯 Task
Design a framework that can:
- Convert a **single JSON topology** into valid **Terraform configurations**
- Support **multi-cloud (AWS & OpenStack)** deployments
- Use **Cloud-Init** to bootstrap VMs automatically
- Offer both **CLI** and **Web UI** to manage infrastructure deployments

---

### ⚡ Action
- Developed Python modules to parse JSON topology and generate `.tf` code
- Implemented CLI tool to generate & apply Terraform configs automatically
- Built a Web UI using **React + FastAPI**, with Docker Compose for deployment
- Integrated **Cloud-Init** scripts to bootstrap VMs with initial setup
- Designed reusable modules for:
  - **AWS**: `aws_instance`, `aws_vpc`, `aws_subnet`, `aws_security_group`, `aws_nat_gateway`, `aws_internet_gateway`, `aws_eip`, `aws_key_pair`, `aws_route_table`...
  - **OpenStack**: `openstack_compute_instance`, `openstack_networking_network`, `openstack_networking_subnet`, `openstack_networking_router`, `openstack_networking_floatingip`, `openstack_compute_keypair`, `openstack_networking_secgroup`...
---

### 🏆 Result
- Reduced provisioning time from **hours to a few minutes** per environment
- Enabled **one-click deployments** of complex topologies on AWS/OpenStack
- Eliminated human errors in `.tf` configuration by generating it automatically
- Easily replicated environments (e.g. create 3 identical clusters with one command)
- Provided a clear architecture and workflow, helping others onboard faster

---

## 🏗️ System Architecture

<p align="center">
  <img src="https://i.postimg.cc/QCmH7LDT/KIentruc.png" alt="Architecture" width="720"/>
</p>

---

## ⚙️ Workflow

<p align="center">
  <img src="https://i.postimg.cc/fytrtsmH/luonghoatodong.png" alt="Workflow" width="720"/>
</p>

1. User defines `topology.json`
2. CLI triggers the generator
3. Terraform `.tf` files are created for target cloud
4. Terraform applies infrastructure
5. Cloud-Init scripts configure instances automatically

---

## 📄 Sample `topology.json`

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
      "networks": [{ "name": "net1", "ip": "192.168.1.10" }],
      "keypair": "toanndcloud-keypair",
      "security_groups": ["default"],
      "floating_ip": true
    }
  ],
  "networks": [
    {
      "name": "net1",
      "cidr": "192.168.1.0/24",
      "gateway_ip": "192.168.1.1",
      "enable_dhcp": true
    }
  ],
  "routers": [
    {
      "name": "R1",
      "networks": [{ "name": "net1", "ip": "192.168.1.1" }],
      "external": true
    }
  ]
}
```
## 🖥️ Result Example
<p align="center">
  <img src="https://i.postimg.cc/PJTMhkKp/Screenshot-2025-08-22-161416.png" alt="Result" width="720"/>
</p>

---

## 🧪 CLI Usage

### 📌 Prerequisites

```bash
sudo apt update && sudo apt install python3 python3-pip unzip -y
wget https://releases.hashicorp.com/terraform/1.6.6/terraform_1.6.6_linux_amd64.zip
unzip terraform_1.6.6_linux_amd64.zip && sudo mv terraform /usr/local/bin/
pip install awscli python-openstackclient
```
### 📝 Prepare Credentials

Create a file named `terraform-generator/openstack/credentials.tfvars`:

```hcl
openstack_auth_url     = ""
openstack_region       = ""
openstack_tenant_name  = ""
openstack_user_name    = ""
openstack_password     = ""
external_network_id    = ""
```

### 💻 CLI Command
python3 generate.py [openstack|aws] <number_of_copies>

## 🌐 Web UI Usage
### 📌 Prerequisites
Docker & Docker Compose
Node.js & npm

### 🔐 AWS SSO Setup
```bash
aws configure sso --profile my-sso
aws sso login --profile my-sso
```
### 🖥️ Run Backend & Frontend
```bash
docker compose up --build
cd frontend && npm start
