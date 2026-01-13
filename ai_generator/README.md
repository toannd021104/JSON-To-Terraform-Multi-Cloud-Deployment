# AI Topology Generator

AI-powered tool to generate topology.json files using OpenAI GPT-4o-mini.

## Features

- Generate complete topology with instances, networks, and routers
- Interactive mode with beautiful CLI
- Command-line mode for scripting
- Auto-validation and retry mechanism
- Professional output styling

## Installation

```bash
pip install typer rich questionary openai
export OPENAI_API_KEY='sk-...'
```

## Usage

### Interactive Mode

```bash
python3 ai_generator/topology_generator.py interactive
```

### Command Line Mode

```bash
# Basic usage
python3 ai_generator/topology_generator.py generate \
  "3 VMs with 2 CPUs each on 192.168.1.0/24"

# Custom output
python3 ai_generator/topology_generator.py generate \
  "Kubernetes cluster with 5 nodes" \
  --output custom.json

# Show full JSON
python3 ai_generator/topology_generator.py generate \
  "Simple 2 VM setup" \
  --json

# Disable preview
python3 ai_generator/topology_generator.py generate \
  "3 web servers" \
  --no-preview
```

### Show Examples

```bash
python3 ai_generator/topology_generator.py examples
```

### Help

```bash
python3 ai_generator/topology_generator.py --help
```

## Output

Generated topology.json will be saved to:
```
generate/topology.json
```

Then you can run:
```bash
cd generate
python3 terraform_generator.py [aws|openstack] <copies>
```

## Requirements

- Python 3.8+
- OpenAI API key
- Dependencies: typer, rich, questionary, openai
