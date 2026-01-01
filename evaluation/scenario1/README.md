# Kịch bản 1: Đánh giá tính đúng đắn End-to-End

## Mục tiêu

Đánh giá tính đúng đắn end-to-end của hệ thống sinh mã Terraform từ mô hình JSON với độ phức tạp topology tăng dần.

## Các Topology được đánh giá

| Topology     | Instances | Networks | Routers | Transit Networks | Độ phức tạp |
| ------------ | --------- | -------- | ------- | ---------------- | ----------- |
| tn1a         | 2         | 1        | 1       | 0                | Đơn giản    |
| tn1b-2router | 2         | 3        | 2       | 1                | Trung bình  |
| tn1c         | 4         | 9        | 4       | 5                | Phức tạp    |

## Mô hình đánh giá 4 tầng

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer A: INPUT VALIDATION                                      │
│  - Schema Validation (JSON Schema)                              │
│  - Logic Validation (CIDR, references, duplicates)              │
├─────────────────────────────────────────────────────────────────┤
│  Layer B: TERRAFORM DEPLOYMENT                                  │
│  - terraform init/plan/apply                                    │
│  - Resource count, Duration, Success rate                       │
├─────────────────────────────────────────────────────────────────┤
│  Layer C: MODEL CONSISTENCY                                     │
│  - So sánh JSON với Terraform State                             │
│  - Networks, Instances, Routers matching                        │
├─────────────────────────────────────────────────────────────────┤
│  Layer D: USER-DATA VERIFICATION                                │
│  - Cloud-init file existence                                    │
│  - Configuration checklist validation                           │
└─────────────────────────────────────────────────────────────────┘
```

## Cách chạy

```bash
cd /home/ubuntu/JSON-To-Terraform-Multi-Cloud-Deployment
./evaluation/scenario1/evaluate_topologies_v2.sh
```

## Kết quả mẫu

```
==========================================================================================
BẢNG KẾT QUẢ ĐÁNH GIÁ 4 LAYERS
==========================================================================================

📋 LAYER A - INPUT VALIDATION
----------------------------------------------------------------------
Topology                  Schema       Logic        Kết quả
----------------------------------------------------------------------
topology-tn1a             PASS         PASS         Hợp lệ
topology-tn1b-2router     PASS         PASS         Hợp lệ
topology-tn1c             PASS         PASS         Hợp lệ

📋 LAYER B - TERRAFORM DEPLOYMENT
----------------------------------------------------------------------
Topology                  Apply        Resources    Duration
----------------------------------------------------------------------
topology-tn1a             Success      9            49s
topology-tn1b-2router     Success      22           52s
topology-tn1c             Success      68           75s

📋 LAYER C - MODEL CONSISTENCY
----------------------------------------------------------------------
Topology                  Networks     Instances    Routers      Match Rate
----------------------------------------------------------------------
topology-tn1a             PASS         PASS         PASS         100%
topology-tn1b-2router     PASS         PASS         PASS         100%
topology-tn1c             PASS         PASS         PASS         100%

📋 LAYER D - USER-DATA VERIFICATION
----------------------------------------------------------------------
Topology                  VMs        Cloud-init    Kết quả
----------------------------------------------------------------------
topology-tn1a             2          2             2/2 VMs configured
topology-tn1b-2router     2          2             2/2 VMs configured
topology-tn1c             4          4             4/4 VMs configured

==========================================================================================
TỔNG HỢP: 3/3 topologies passed all 4 layers
==========================================================================================
```

## Output

Kết quả được lưu tại: `evaluation/results/comparative_YYYYMMDD_HHMMSS/`

```
results/comparative_YYYYMMDD_HHMMSS/
├── topology-tn1a/
│   ├── layer_a_result.json
│   ├── layer_b_result.json
│   ├── layer_c_result.json
│   ├── layer_d_result.json
│   └── summary.json
├── topology-tn1b-2router/
│   └── ...
├── topology-tn1c/
│   └── ...
└── comparison_report.json
```
