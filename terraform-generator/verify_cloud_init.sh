#!/bin/bash
# Script to verify cloud-init integration in generated Terraform projects

echo "=========================================="
echo "CLOUD-INIT INTEGRATION VERIFICATION"
echo "=========================================="
echo ""

# Find latest terraform project
LATEST_PROJECT=$(ls -td ../terraform-projects/openstack_* 2>/dev/null | head -1)

if [ -z "$LATEST_PROJECT" ]; then
    echo "❌ No Terraform projects found in ../terraform-projects/"
    echo "   Run: python3 generate.py openstack 1"
    exit 1
fi

echo "📁 Checking latest project: $(basename $LATEST_PROJECT)"
echo ""

# Find all subdirectories
for DIR in "$LATEST_PROJECT"/openstack_*; do
    if [ ! -d "$DIR" ]; then
        continue
    fi

    echo "─────────────────────────────────────────"
    echo "📂 Directory: $(basename $DIR)"
    echo "─────────────────────────────────────────"

    # Check if cloud_init directory exists
    if [ -d "$DIR/cloud_init" ]; then
        YAML_COUNT=$(find "$DIR/cloud_init" -name "*.yaml" -type f 2>/dev/null | wc -l)
        echo "  ✅ cloud_init/ directory exists"
        echo "  📄 Found $YAML_COUNT YAML file(s):"

        # List YAML files
        find "$DIR/cloud_init" -name "*.yaml" -type f 2>/dev/null | while read YAML_FILE; do
            echo "     - $(basename $YAML_FILE)"
        done
    else
        echo "  ⚠️  cloud_init/ directory not found"
    fi

    # Check topology.json for cloud_init references
    if [ -f "$DIR/topology.json" ]; then
        CLOUD_INIT_REFS=$(grep -c '"cloud_init"' "$DIR/topology.json" 2>/dev/null || echo "0")
        if [ "$CLOUD_INIT_REFS" -gt 0 ]; then
            echo "  ✅ topology.json has cloud_init references: $CLOUD_INIT_REFS"

            # Show which instances use cloud-init
            echo "  📋 Instances with cloud-init:"
            grep -B2 '"cloud_init"' "$DIR/topology.json" | grep '"name"' | sed 's/.*"name": "\(.*\)".*/     - \1/'
        else
            echo "  ⚠️  topology.json has NO cloud_init references"
        fi
    fi

    # Check main.tf for user_data
    if [ -f "$DIR/main.tf" ]; then
        if grep -q "user_data" "$DIR/main.tf" 2>/dev/null; then
            echo "  ✅ main.tf contains user_data configuration"
        else
            echo "  ⚠️  main.tf does NOT contain user_data"
        fi
    fi

    echo ""
done

echo "=========================================="
echo "✅ VERIFICATION COMPLETE"
echo "=========================================="
echo ""
echo "To view a generated cloud-init file:"
echo "  cat $LATEST_PROJECT/openstack_*/cloud_init/*.yaml"
echo ""
echo "To check Terraform plan:"
echo "  cd $LATEST_PROJECT/openstack_*/"
echo "  terraform plan | grep user_data"
