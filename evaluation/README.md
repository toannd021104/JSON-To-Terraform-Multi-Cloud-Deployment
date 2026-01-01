# Evaluation Framework

Scientific, reproducible evaluation framework for JSON-To-Terraform Multi-Cloud Deployment pipeline.

## Overview

This framework provides automated evaluation of the entire deployment pipeline across four layers:

- **Layer A**: Input Validation (JSON schema, network logic)
- **Layer B**: Terraform Deployment (init/plan/apply)
- **Layer C**: Model Consistency (topology vs state)
- **Layer D**: User-Data Verification (SSH checklist execution)

All scripts output machine-readable JSON for aggregation and analysis.

## Directory Structure

```
evaluation/
├── evaluator.py                    # Main orchestrator
├── layer_a_validation.py           # Input validation
├── layer_b_terraform.py            # Terraform deployment
├── layer_c_consistency.py          # Consistency checking
├── layer_d_userdata.py             # User-data verification
├── aggregator.py                   # Result aggregation
├── evaluation_config.json          # Main configuration
├── vm_verification_config.json     # VM checklist configuration
├── checklists/                     # Checklist templates
│   └── README.md
└── results/                        # Output directory (auto-generated)
```

## Quick Start

### 1. Configure Evaluation

Edit `evaluation_config.json`:

```json
{
  "layer_a": {
    "enabled": true,
    "topology_file": "terraform-generator/topology.json"
  },
  "layer_b": {
    "enabled": true,
    "terraform_project_dir": "terraform-projects/openstack_topology_1/openstack_topology_1",
    "cloud_provider": "openstack"
  }
}
```

### 2. Configure VM Verification (Layer D)

Edit `vm_verification_config.json` with your VM IPs and checklist:

```json
{
  "vms": [
    {
      "name": "instance1",
      "host": "10.0.1.10",
      "username": "ubuntu",
      "ssh_key": "~/.ssh/tf-cloud-init",
      "checklist": [
        { "type": "package_installed", "target": "apache2" },
        { "type": "service_running", "target": "apache2" }
      ]
    }
  ]
}
```

### 3. Run Complete Evaluation

```bash
cd evaluation/
chmod +x *.py
./evaluator.py evaluation_config.json
```

### 4. View Results

Results are saved in `evaluation/results/`:

- `final_report.json` - Machine-readable full report
- `final_report.txt` - Human-readable summary table
- `final_report.csv` - CSV for spreadsheet import
- `layer_*_result.json` - Individual layer results

## Running Individual Layers

### Layer A: Input Validation

```bash
./layer_a_validation.py \
  terraform-generator/topology.json \
  results/layer_a_result.json \
  cloud-init-generator/cloud_init.json
```

**Output metrics:**

- Schema validation pass/fail
- Network logic validation
- Error count and details
- Pass rate percentage

### Layer B: Terraform Deployment

```bash
./layer_b_terraform.py \
  terraform-projects/openstack_topology_1/openstack_topology_1 \
  openstack \
  results/layer_b_result.json
```

**Output metrics:**

- Init/validate/plan/apply status
- Resources planned/created
- Execution time per phase
- Success rate

**Skip apply (plan only):**

```bash
./layer_b_terraform.py ... --skip-apply
```

### Layer C: Model Consistency Check

```bash
./layer_c_consistency.py \
  terraform-generator/topology.json \
  terraform-projects/.../terraform.tfstate \
  openstack \
  results/layer_c_result.json
```

**Output metrics:**

- Network/instance/router consistency
- Count mismatches
- Attribute mismatches (CIDR, flavor, image)
- Consistency rate

### Layer D: User-Data Verification

```bash
./layer_d_userdata.py \
  vm_verification_config.json \
  results/layer_d_result.json
```

**Output metrics:**

- VM accessibility (SSH)
- Per-VM check results
- Pass/fail per check type
- VM and check pass rates

## Result Aggregation

Aggregate all layer results into final report:

```bash
./aggregator.py results/ \
  --output final_report.json \
  --text final_report.txt \
  --csv final_report.csv
```

## Cloud Provider Support

### OpenStack

```json
{
  "layer_b": {
    "cloud_provider": "openstack",
    "terraform_project_dir": "terraform-projects/openstack_*/openstack_*/"
  }
}
```

### AWS

```json
{
  "layer_b": {
    "cloud_provider": "aws",
    "terraform_project_dir": "terraform-projects/aws_*/aws_*/"
  }
}
```

## Checklist Configuration

### Available Check Types

1. **package_installed**: Verify package installation

   ```json
   { "type": "package_installed", "target": "apache2" }
   ```

2. **service_running**: Check service status

   ```json
   { "type": "service_running", "target": "nginx" }
   ```

3. **file_exists**: Verify file presence

   ```json
   { "type": "file_exists", "target": "/etc/config.conf" }
   ```

4. **directory_exists**: Verify directory presence

   ```json
   { "type": "directory_exists", "target": "/var/log/app" }
   ```

5. **user_exists**: Check user account

   ```json
   { "type": "user_exists", "target": "appuser" }
   ```

6. **command_output**: Verify command output

   ```json
   { "type": "command_output", "command": "hostname", "expected": "web-server" }
   ```

7. **network_connectivity**: Test network reachability
   ```json
   { "type": "network_connectivity", "target": "8.8.8.8" }
   ```

See `checklists/README.md` for templates.

## Output Format

All scripts output JSON with consistent structure:

```json
{
  "layer": "LAYER_NAME",
  "timestamp": "2025-12-25T...",
  "status": "PASS|FAIL|PARTIAL|ERROR",
  "summary": {
    "pass_rate": "95.00%",
    ...
  },
  "errors": []
}
```

## Exit Codes

- `0`: Success/Pass
- `1`: Failure/Errors

## Use in Graduation Thesis

### Academic Rigor

1. **Reproducibility**: All evaluations use fixed configurations
2. **Objectivity**: Machine-based measurement, no human interpretation
3. **Comprehensiveness**: Four independent evaluation dimensions
4. **Quantifiable**: All metrics are numerical or percentages

### Thesis Structure

Include these metrics in your thesis:

**Table 4.1: Input Validation Results**

- Schema validation accuracy
- Error detection rate
- Validation time

**Table 4.2: Deployment Performance**

- Success rate by cloud provider
- Resource creation time
- Multi-copy scalability

**Table 4.3: Model Consistency**

- Consistency rate
- Mismatch types and frequency
- Resource accuracy by type

**Table 4.4: User-Data Execution**

- VM accessibility rate
- Check execution success rate
- Service availability

### Generate Thesis Tables

```bash
# Run evaluation
./evaluator.py evaluation_config.json

# Extract metrics for thesis
python3 << 'EOF'
import json
with open('results/final_report.json') as f:
    report = json.load(f)
    for layer, metrics in report['layers'].items():
        print(f"\n{layer}:")
        for k, v in metrics.items():
            print(f"  {k}: {v}")
EOF
```

## Troubleshooting

### SSH Connection Failed

- Verify floating IPs are assigned
- Check security group allows SSH (port 22)
- Ensure SSH key path is correct
- Increase `ssh_timeout` in config

### Terraform State Not Found

- Run Layer B with `skip_apply: false`
- Check `terraform_project_dir` path
- Ensure terraform apply completed successfully

### Cloud-Init Not Complete

- Increase `cloud_init_wait` time (default: 120s)
- Check cloud-init logs: `ssh vm "sudo cloud-init status"`

## Advanced Usage

### Batch Evaluation

Evaluate multiple topologies:

```bash
for config in configs/*.json; do
    ./evaluator.py "$config"
done
```

### Continuous Evaluation

```bash
while true; do
    ./evaluator.py evaluation_config.json
    sleep 3600  # Every hour
done
```

### Custom Metrics

Extend scripts by adding new check types in `layer_d_userdata.py`:

```python
def verify_custom_check(self, host, username, key_file, params):
    # Your custom verification logic
    pass
```

## Requirements

- Python 3.6+
- Terraform
- SSH client
- Cloud provider credentials configured

No additional Python packages required (uses stdlib only).

## License

Part of JSON-To-Terraform Multi-Cloud Deployment project.
