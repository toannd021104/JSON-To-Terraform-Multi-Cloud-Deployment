#!/bin/bash
# Script chạy kịch bản 2 đơn giản

cd "$(dirname "$0")/../.."

MODE=${1:-quick}

echo "========================================"
echo "  KỊCH BẢN 2: ĐÁNH GIÁ KHẢ NĂNG MỞ RỘNG"
echo "========================================"
echo "Mode: $MODE"
echo ""

python3 evaluation/scenario2/scenario2_scalability.py --mode "$MODE"
