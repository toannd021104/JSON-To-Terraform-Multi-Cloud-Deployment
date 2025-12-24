# OpenStack Configuration Manager

## Tổng quan

Hệ thống tự động quản lý nhiều profile OpenStack khác nhau và tự động discover các resources cần thiết.

## Cấu trúc

```
openstack_config.json          # File cấu hình chính (chứa credentials)
openstack_config.json.template # Template mẫu
openstack_config_manager.py    # Module quản lý config
```

## Cách sử dụng

### 1. Setup Profile Mới (Interactive)

```bash
python3 openstack_config_manager.py setup
```

Sẽ hỏi:

- Profile name (default: "default")
- Auth URL (http://IP:5000)
- Region (RegionOne)
- Project Name
- Username
- Password

### 2. Liệt kê các Profile

```bash
python3 openstack_config_manager.py list
```

### 3. Chuyển đổi Profile

```bash
python3 openstack_config_manager.py switch --profile <profile_name>
```

### 4. Auto-discover Resources

```bash
python3 openstack_config_manager.py discover
```

Tự động tìm:

- External network (name + ID)
- Service endpoints
- Available images
- Available flavors

### 5. Export sang Terraform Variables

```bash
python3 openstack_config_manager.py export --output terraform.tfvars
```

## File cấu hình (openstack_config.json)

```json
{
  "profiles": {
    "default": {
      "auth_url": "http://10.102.192.230:5000",
      "region": "RegionOne",
      "project_name": "dacn",
      "username": "dacn",
      "password": "your_password",
      "user_domain_name": "Default",
      "project_domain_id": "default"
    },
    "alternate": {
      "auth_url": "http://another-ip:5000",
      "region": "RegionOne",
      "project_name": "another_project",
      "username": "another_user",
      "password": "another_password",
      "user_domain_name": "Default",
      "project_domain_id": "default"
    }
  },
  "active_profile": "default",
  "auto_discover": {
    "external_network": true,
    "endpoints": true,
    "images": true,
    "flavors": true
  }
}
```

## Tích hợp với Generate.py

Khi chạy `python3 generate.py openstack 1`, hệ thống sẽ:

1. **Tự động load** `openstack_config.json`
2. **Discover** external network và endpoints
3. **Tự động fill** vào `variables.tf`
4. **Không cần** hardcode credentials nữa

## Ví dụ Workflow

### Scenario 1: Đổi sang OpenStack endpoint khác

```bash
# 1. Tạo profile mới
python3 openstack_config_manager.py setup
# Nhập thông tin endpoint mới

# 2. Chuyển sang profile mới
python3 openstack_config_manager.py switch --profile new_profile

# 3. Generate Terraform như bình thường
python3 generate.py openstack 1
# Tự động dùng credentials từ profile mới
```

### Scenario 2: Thêm profile cho môi trường test/prod

```json
{
  "profiles": {
    "test": {
      "auth_url": "http://test-openstack:5000",
      "project_name": "test-project",
      ...
    },
    "prod": {
      "auth_url": "http://prod-openstack:5000",
      "project_name": "prod-project",
      ...
    }
  }
}
```

```bash
# Deploy lên test
python3 openstack_config_manager.py switch --profile test
python3 generate.py openstack 1

# Deploy lên prod
python3 openstack_config_manager.py switch --profile prod
python3 generate.py openstack 1
```

## Lợi ích

✅ **Không hardcode**: Credentials và endpoints được quản lý tập trung
✅ **Multi-environment**: Dễ dàng switch giữa nhiều môi trường
✅ **Auto-discovery**: Tự động phát hiện external network, endpoints
✅ **Version control friendly**: Template file có thể commit, config file thì gitignore
✅ **Security**: Credentials không bị hardcode trong code

## Cài đặt Dependencies

```bash
# Để sử dụng auto-discovery
pip install openstacksdk

# Optional: Rich terminal output
pip install rich
```

## Gitignore

Nhớ thêm vào `.gitignore`:

```
openstack_config.json
terraform.tfvars
*.tfstate*
```

## Troubleshooting

### Lỗi "No config found"

→ Chạy `python3 openstack_config_manager.py setup` để tạo config

### Lỗi "OpenStack SDK not available"

→ Cài: `pip install openstacksdk`

### Discovery không hoạt động

→ Kiểm tra credentials và network connectivity đến OpenStack endpoint
