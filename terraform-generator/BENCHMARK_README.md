# Deployment Benchmark & Testing

Scripts để test và benchmark việc tạo nhiều bản sao infrastructure.

## 📋 Scripts có sẵn

### 1. `benchmark_deployment.py` - Script chính

Script đầy đủ với tất cả tính năng:
- ⏱️ Đo thời gian deployment
- 📦 Track tài nguyên được tạo
- 💾 Lưu kết quả vào file JSON
- 🗑️ Option cleanup tự động hoặc hỏi user

**Cách dùng:**

```bash
# Cú pháp cơ bản
python3 benchmark_deployment.py <provider> <số_copies> [options]

# Test AWS với 3 copies, hỏi có xóa không
python3 benchmark_deployment.py aws 3

# Test OpenStack với 2 copies, tự động xóa sau khi test
python3 benchmark_deployment.py openstack 2 --auto-cleanup

# Test AWS với 5 copies, giữ lại resources
python3 benchmark_deployment.py aws 5 --no-cleanup
```

**Options:**
- `--auto-cleanup`: Tự động xóa resources sau khi test xong
- `--no-cleanup`: Giữ lại resources, không hỏi

### 2. `quick_test.py` - Script nhanh

Wrapper đơn giản, luôn hỏi có xóa không.

```bash
python3 quick_test.py aws 2
python3 quick_test.py openstack 1
```

## 📊 Output Files

Kết quả được lưu vào folder `benchmark_logs/`:

```
benchmark_logs/
└── benchmark_aws_3copies_20250110_152030.json
```

### Format file kết quả:

```json
{
  "provider": "aws",
  "num_copies": 3,
  "timestamp": "2025-01-10T15:20:30.123456",
  "stages": {
    "generate": {
      "duration_seconds": 125.45,
      "duration_formatted": "2m 5.45s",
      "project_folder": "/path/to/terraform-projects/aws_20250110_152030"
    },
    "cleanup": {
      "duration_seconds": 89.32,
      "duration_formatted": "1m 29.32s",
      "success": true
    }
  },
  "resources_created": {
    "00-shared-vpc": {
      "aws_vpc": 1,
      "aws_subnet": 9,
      "aws_nat_gateway": 1,
      "aws_instance": 1,
      "total": 25
    },
    "aws_a1b2c3": {
      "instances": 2,
      "total": 5
    },
    "aws_d4e5f6": {
      "instances": 2,
      "total": 5
    }
  },
  "total_time": 214.77,
  "total_time_formatted": "3m 34.77s"
}
```

## 🎯 Use Cases

### Test performance với số lượng copies khác nhau

```bash
# Test 1 copy
python3 benchmark_deployment.py aws 1 --auto-cleanup

# Test 3 copies
python3 benchmark_deployment.py aws 3 --auto-cleanup

# Test 5 copies
python3 benchmark_deployment.py aws 5 --auto-cleanup

# So sánh kết quả trong benchmark_logs/
```

### Verify deployment thành công

```bash
# Deploy nhưng không xóa, để kiểm tra manually
python3 benchmark_deployment.py aws 2 --no-cleanup

# Kiểm tra resources
cd ../terraform-projects/aws_<timestamp>
terraform state list

# Xóa khi đã kiểm tra xong
python3 run_terraform.py destroy
```

### Demo shared VPC benefits

```bash
# Tạo 3 copies và xem resources
python3 benchmark_deployment.py aws 3

# Kiểm tra:
# - 00-shared-vpc/ folder (1 VPC, 1 NAT, 1 Bastion)
# - 3 instance folders (chỉ có EC2 instances)
```

## 📈 Benchmark Results Example

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  BENCHMARK SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Provider: aws
Number of copies: 3
Timestamp: 2025-01-10T15:20:30.123456

⏱️  Timing:
  - Generate: 2m 5.45s
  - Cleanup: 1m 29.32s
  - Total: 3m 34.77s

📦 Resources Summary:
  - aws_a1b2c3: 2 instances
  - aws_d4e5f6: 2 instances
  - aws_x9y8z7: 2 instances

  Total instances: 6

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## ⚠️ Lưu ý

1. **Chi phí AWS/OpenStack**: Mỗi lần chạy sẽ tạo resources thực sự → tốn tiền!
2. **Cleanup quan trọng**: Luôn destroy resources sau khi test xong
3. **Số lượng copies**: Script sẽ cảnh báo nếu > 10 copies
4. **Prerequisites**:
   - AWS credentials configured (cho AWS)
   - OpenStack credentials sourced (cho OpenStack)
   - Terraform installed
   - topology.json hợp lệ

## 🔍 Troubleshooting

### Script báo lỗi "Project folder not found"

```bash
# Kiểm tra terraform-projects/ folder tồn tại
ls -la ../terraform-projects/

# Có thể folder đã bị xóa hoặc generate fail
```

### Cleanup fail

```bash
# Manual cleanup
cd ../terraform-projects/aws_<timestamp>
python3 run_terraform.py destroy

# Hoặc cleanup từng folder
cd 00-shared-vpc
terraform destroy -auto-approve
```

### State file không tồn tại

Có thể terraform apply chưa chạy hoặc fail. Check logs trong quá trình generate.

## 📝 Tips

- Dùng `--auto-cleanup` khi test automation/CI
- Dùng mặc định (prompt) khi test manual để có thể inspect resources
- Check `benchmark_logs/` để so sánh performance qua các lần test
- Combine với git để track performance improvements over time
