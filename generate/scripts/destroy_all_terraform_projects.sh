#!/bin/bash

# Script to run terraform destroy on all project folders
# Usage: cd generate && ./scripts/destroy_all_terraform_projects.sh

set +e  # Don't exit on error

echo "=========================================="
echo "Terraform Destroy All Projects"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Navigate to terraform-projects directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
TERRAFORM_PROJECTS_DIR="$PROJECT_ROOT/terraform-projects"

if [ ! -d "$TERRAFORM_PROJECTS_DIR" ]; then
    echo -e "${RED}Error: terraform-projects directory not found${NC}"
    echo "Expected: $TERRAFORM_PROJECTS_DIR"
    exit 1
fi

cd "$TERRAFORM_PROJECTS_DIR"

# Get all project folders (openstack_* and aws_* patterns)
project_dirs=$(find . -maxdepth 1 -type d \( -name "openstack_*" -o -name "aws_*" \) | sort -r)

if [ -z "$project_dirs" ]; then
    echo -e "${YELLOW}No project folders found${NC}"
    exit 0
fi

# Count projects
total=$(echo "$project_dirs" | wc -l)
current=0

echo -e "${CYAN}Found $total project(s) to destroy:${NC}"
echo "$project_dirs" | while read -r dir; do
    echo "  - $dir"
done
echo ""

# Ask for confirmation
echo -e "${YELLOW}⚠️  WARNING: This will destroy ALL resources in ALL projects!${NC}"
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo -e "${GREEN}Aborted${NC}"
    exit 0
fi

echo ""
echo "=========================================="
echo "Starting destroy process..."
echo "=========================================="
echo ""

# Process each project directory
echo "$project_dirs" | while read -r dir; do
    current=$((current + 1))
    project_name=$(basename "$dir")
    
    echo ""
    echo "=========================================="
    echo -e "${CYAN}[$current/$total] Processing: $project_name${NC}"
    echo "=========================================="
    
    # Check if run_terraform.py exists
    if [ -f "$dir/run_terraform.py" ]; then
        echo -e "${GREEN}✓${NC} Found run_terraform.py"
        echo -e "Running: ${CYAN}python3 run_terraform.py destroy${NC}"
        echo ""
        
        cd "$dir"
        python3 run_terraform.py destroy
        exit_code=$?
        cd - > /dev/null
        
        if [ $exit_code -eq 0 ]; then
            echo ""
            echo -e "${GREEN}✓ Successfully destroyed $project_name${NC}"
        else
            echo ""
            echo -e "${RED}✗ Failed to destroy $project_name (exit code: $exit_code)${NC}"
        fi
    else
        echo -e "${YELLOW}⚠  run_terraform.py not found, skipping${NC}"
    fi
done

echo ""
echo "=========================================="
echo -e "${GREEN}Destroy process completed!${NC}"
echo "=========================================="
echo ""

# Check which cloud provider to verify
echo "Verifying remaining resources..."
echo ""

# Try OpenStack CLI if available
if command -v openstack &> /dev/null; then
    echo "Checking OpenStack resources:"
    openstack server list 2>/dev/null || echo "Could not check instances"
    echo ""
    openstack router list 2>/dev/null || echo "Could not check routers"
    echo ""
    openstack network list 2>/dev/null | grep -v "public" || echo "Could not check networks"
fi

# Try AWS CLI if available
if command -v aws &> /dev/null; then
    echo ""
    echo "Checking AWS resources (may take a moment)..."
    AWS_REGION="${AWS_DEFAULT_REGION:-us-west-2}"
    aws ec2 describe-instances --region "$AWS_REGION" --query 'Reservations[*].Instances[?State.Name==`running`].[InstanceId,Tags[?Key==`Name`].Value|[0]]' --output table 2>/dev/null || echo "Could not check EC2 instances"
fi
