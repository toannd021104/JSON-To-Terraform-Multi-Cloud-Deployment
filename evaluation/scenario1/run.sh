#!/bin/bash
# Script chạy kịch bản 1 đơn giản

cd "$(dirname "$0")/../.."

echo "========================================"
echo "  KỊCH BẢN 1: ĐÁNH GIÁ TÍNH ĐÚNG ĐẮN"
echo "========================================"
echo ""

./evaluation/scenario1/evaluate_topologies_v2.sh
