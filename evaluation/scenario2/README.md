# Kịch bản 2: Đánh giá khả năng mở rộng và nhân bản hạ tầng

## Mục tiêu

So sánh việc triển khai nhiều bản sao của cùng một topology giữa cách làm thủ công và framework đề xuất nhằm đánh giá khả năng mở rộng và tối ưu thời gian.

## Topology sử dụng

```
topology-scenario2.json
├── 1 Instance (pc1)
├── 1 Network (web-net: 192.168.10.0/24)
└── 1 Router (edge-router)
```

## Cách chạy

### Cú pháp

```bash
python3 evaluation/scenario2/scenario2_scalability.py [N1,N2,N3,...]
```

### Ví dụ

```bash
# Mặc định (N=1,3,5)
python3 evaluation/scenario2/scenario2_scalability.py

# Tự chọn N
python3 evaluation/scenario2/scenario2_scalability.py 1,3,5,10,20

# Full test
python3 evaluation/scenario2/scenario2_scalability.py 1,3,5,10,20,40,60,100

# Với topology file khác
python3 evaluation/scenario2/scenario2_scalability.py 1,3,5 path/to/topology.json
```

## Chỉ số đánh giá

| Chỉ số        | Mô tả                                     |
| ------------- | ----------------------------------------- |
| Thời gian (s) | Tổng thời gian generate + terraform apply |
| Resources     | Số lượng tài nguyên được tạo              |
| Folders       | Số thư mục bản sao được tạo               |
| Success       | Triển khai thành công hay không           |
| Name Dup      | Số tên tài nguyên bị trùng (phải = 0)     |
| Consistent    | Các bản sao có cùng cấu trúc không        |

## Kết quả mẫu

```
================================================================================
KỊCH BẢN 2: ĐÁNH GIÁ KHẢ NĂNG MỞ RỘNG VÀ NHÂN BẢN HẠ TẦNG
================================================================================
Topology: topology-scenario2.json
Các giá trị N: [1, 3, 5, 10, 20]

==========================================================================================
BÁO CÁO KẾT QUẢ KỊCH BẢN 2
==========================================================================================

📊 BẢNG KẾT QUẢ:
------------------------------------------------------------------------------------------
     N |   Thời gian (s) |  Resources |  Folders |  Success |  Name Dup | Consistent
------------------------------------------------------------------------------------------
     1 |           47.56 |          7 |        1 |        ✓ |         0 |          ✓
     3 |           57.95 |         21 |        3 |        ✓ |         0 |          ✓
     5 |           71.86 |         35 |        5 |        ✓ |         0 |          ✓
    10 |          125.32 |         70 |       10 |        ✓ |         0 |          ✓
    20 |          245.67 |        140 |       20 |        ✓ |         0 |          ✓
------------------------------------------------------------------------------------------

📈 TỔNG KẾT:
  • Tổng số bản sao: 39
  • Tổng thời gian: 548.36s
  • Tổng resources: 273
  • Tỷ lệ thành công: 5/5 (100%)
  • Số trùng tên: 0
  • Cấu trúc nhất quán: ✓ Có

📊 PHÂN TÍCH THỜI GIAN:
  • N=3: Framework 57.9s vs Thủ công (ước) 142.7s → Tiết kiệm 84.8s (2.5x)
  • N=5: Framework 71.9s vs Thủ công (ước) 237.8s → Tiết kiệm 165.9s (3.3x)
  • N=10: Framework 125.3s vs Thủ công (ước) 475.6s → Tiết kiệm 350.3s (3.8x)
  • N=20: Framework 245.7s vs Thủ công (ước) 951.2s → Tiết kiệm 705.5s (3.9x)
```

## Output

Kết quả được lưu tại: `evaluation/results/scenario2_YYYYMMDD_HHMMSS/`

```
results/scenario2_YYYYMMDD_HHMMSS/
└── scenario2_results.json    # Kết quả chi tiết dạng JSON
```

## Dọn dẹp sau khi test

Script tự động destroy và cleanup các terraform projects trước mỗi lần test. Để dọn dẹp thủ công:

```bash
./terraform-generator/scripts/destroy_all_terraform_projects.sh
```

## Files

| File                             | Mô tả                               |
| -------------------------------- | ----------------------------------- |
| `scenario2_scalability.py`       | Script chính chạy đánh giá          |
| `topology-scenario2.json`        | Topology đơn giản dùng cho đánh giá |
| `scenario2_check_duplicates.py`  | (Phụ) Kiểm tra trùng tên tài nguyên |
| `scenario2_check_consistency.py` | (Phụ) Kiểm tra đồng nhất cấu trúc   |
