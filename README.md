# JSON-To-Terraform Multi-Cloud Deployment

A framework for describing cloud infrastructure topology and instance initialization using a unified, provider-agnostic model, and automatically generating Infrastructure as Code artifacts for deployment.

📌 **Objective:** Standardize infrastructure descriptions, catch configuration issues early, and generate multi-cloud IaC from a single declaration.

## Problem Statement

Deploying cloud infrastructure with Infrastructure as Code often exposes platform differences in resource models, syntax, and instance initialization. These gaps make definitions hard to reuse, slow to clone at scale, and prone to hidden networking and user-data mistakes that only surface during apply time.

## Approach

Use a unified, abstract topology model to capture infrastructure independently from any provider. Validate topology and user-data early (schema + semantic checks, optional AI review) before generating platform-specific Terraform. Produce ready-to-apply artifacts that can be cloned into multiple isolated environments with consistent naming.

## Key Features

- Unified topology description using structured JSON/YAML
- Early structural and semantic validation (topology, networking, user-data)
- Automatic Terraform generation for AWS and OpenStack
- Standardized cloud-init/user-data handling for multiple OS targets
- Environment cloning with deterministic suffixing to avoid collisions
- Optional AI assistance to author or auto-fix topology and validate user-data

## Architecture Overview

Input (topology + user-data) → schema + semantic validation (networking, user-data) → platform mapping (AWS/OpenStack) → Terraform and cloud-init artifact generation → deploy with Terraform. An AI helper can propose or fix topology and review user-data where enabled.

## Repository Structure

- ai_generator/          AI-assisted topology authoring CLI
- cloud-init-generator/  Cloud-init templates and validators (schema + AI review)
- terraform-generator/   Topology validation and Terraform artifact generation
- terraform-projects/    Generated Terraform projects per provider/environment
- pre-template/          Supporting templates and assets
- requirements.txt       Python dependencies

## Quick Start

1. Install: `pip install -r requirements.txt` and ensure Terraform is on PATH.  
2. Prepare topology: edit `terraform-generator/topology.json` or use the AI generator (`python3 ai_generator/topology_generator.py interactive`).  
3. Validate and generate Terraform: `cd terraform-generator && python3 generate.py [aws|openstack] <copies>`.  
4. Deploy: `cd ../terraform-projects/<provider>_<suffix> && terraform init && terraform apply`.  

## Scope and Limitations

Focuses on provisioning and initialization. Deep runtime management, observability, and advanced operations are out of scope for now.

## Academic Context

This repository supports a graduation thesis on cloud infrastructure abstraction and automated multi-cloud IaC generation.

## License

This project is for academic and educational purposes.
