# OpenStack Config Manager - Hướng Dẫn Sử Dụng

## 📋 Tổng Quan

**OpenStack Config Manager** là hệ thống quản lý credentials OpenStack tập trung, thay thế cách cũ dùng nhiều file shell script rời rạc (`dacn-openrc.sh`).

### Ưu điểm:

- ✅ **Tập trung**: Tất cả credentials trong 1 file JSON duy nhất
- ✅ **Multi-profile**: Quản lý nhiều môi trường OpenStack (dev, prod, test)
- ✅ **Auto-discovery**: Tự động tìm external network và endpoints
- ✅ **An toàn**: File config được gitignore tự động
- ✅ **Dễ dùng**: CLI commands đơn giản

---

## 🔧 Cài Đặt

```bash
cd terraform-generator

# Cài dependencies (optional nhưng recommended)
pip3 install openstacksdk rich

# Setup profile đầu tiên
python3 openstack_config_manager.py setup
```

Nhập thông tin khi được hỏi:

- **Auth URL**: http://10.102.192.230:5000
- **Region**: RegionOne
- **Project Name**: dacn
- **Username**: your_username
- **Password**: your_password

File `openstack_config.json` sẽ được tạo (đã auto-gitignore).

---

## 📁 Cấu Trúc File Config

```json
{
  "profiles": {
    "default": {
      "auth_url": "http://10.102.192.230:5000",
      "region": "RegionOne",
      "project_name": "dacn",
      "username": "your_user",
      "password": "your_pass",
      "user_domain_name": "Default",
      "project_domain_id": "default"
    }
  },
  "active_profile": "default"
}
```

---

## 🚀 Cách Hoạt Động

### 1️⃣ **Load Credentials**

```python
from openstack_config_manager import OpenStackConfigManager

mgr = OpenStackConfigManager()
mgr.load_config()  # Đọc từ openstack_config.json

profile = mgr.get_active_profile()
# Returns: {'auth_url': '...', 'username': '...', 'password': '...'}
```

### 2️⃣ **Set Environment Variables**

Các tool sử dụng config tự động set biến môi trường:

```python
os.environ['OS_AUTH_URL'] = profile['auth_url']
os.environ['OS_PROJECT_NAME'] = profile['project_name']
os.environ['OS_USERNAME'] = profile['username']
os.environ['OS_PASSWORD'] = profile['password']
# ... các biến khác
```

### 3️⃣ **OpenStack CLI Tự Động Nhận**

Khi chạy lệnh OpenStack CLI, nó tự đọc biến môi trường:

```bash
openstack image list    # ✅ Tự động dùng credentials từ profile
openstack server list   # ✅ Không cần source shell script
```

### 4️⃣ **Auto-Discovery**

Tự động tìm external network và endpoints:

```bash
python3 openstack_config_manager.py discover
```

Output:

```json
{
  "external_network": {
    "id": "c668f27f-c14b-410d-b1df-016adc280c6e",
    "name": "public-network"
  },
  "endpoints": {
    "compute": "http://10.102.192.230:8774/v2.1",
    "network": "http://10.102.192.230:9696/"
  }
}
```

---

## 💻 CLI Commands

### Setup Profile Mới

```bash
python3 openstack_config_manager.py setup
```

### Xem Danh Sách Profiles

```bash
python3 openstack_config_manager.py list
```

Output:

```
┌─────────┬────────────────────────────┬─────────┬────────┐
│ Profile │ Auth URL                   │ Project │ Active │
├─────────┼────────────────────────────┼─────────┼────────┤
│ default │ http://10.102.192.230:5000 │ dacn    │ ✓      │
│ prod    │ http://prod.example:5000   │ prod    │        │
└─────────┴────────────────────────────┴─────────┴────────┘
```

### Chuyển Đổi Profile

```bash
python3 openstack_config_manager.py switch --profile prod
```

### Tự Động Khám Phá Tài Nguyên

```bash
python3 openstack_config_manager.py discover
```

### Export Ra Terraform Variables

```bash
python3 openstack_config_manager.py export --output terraform.tfvars
```

---

## 🔗 Tích Hợp Vào Code

### Trong `generate.py`

```python
from openstack_config_manager import OpenStackConfigManager

mgr = OpenStackConfigManager()
if mgr.load_config():
    profile = mgr.get_active_profile()
    discovered = mgr.discover_resources()

    # Tự động điền external_network_name vào variables.tf
    external_net = discovered['external_network']['name']
```

### Trong `validate_openstack.py`

```python
def load_openstack_credentials():
    mgr = OpenStackConfigManager()
    if mgr.load_config():
        profile = mgr.get_active_profile()

        # Set env vars cho OpenStack CLI
        os.environ['OS_AUTH_URL'] = profile['auth_url']
        os.environ['OS_USERNAME'] = profile['username']
        # ...
```

---

## 🔐 Bảo Mật

File `openstack_config.json` chứa **passwords dạng plaintext** nên:

✅ **Đã được gitignore tự động**  
✅ **Không commit lên Git**  
✅ **Chỉ lưu trên máy local**

Pattern trong `.gitignore`:

```
openstack_config.json
*openrc*.sh
*.tfvars
terraform.tfstate*
```

---

## 🆚 So Sánh: Cũ vs Mới

| Đặc điểm         | Cách Cũ (Shell Script)               | Cách Mới (Config Manager)  |
| ---------------- | ------------------------------------ | -------------------------- |
| File credentials | `dacn-openrc.sh`, `dacn-openrc-2.sh` | `openstack_config.json`    |
| Số file          | Nhiều file rời rạc                   | 1 file duy nhất            |
| Multi-profile    | ❌ Không hỗ trợ                      | ✅ Hỗ trợ nhiều profiles   |
| Auto-discovery   | ❌ Phải hardcode                     | ✅ Tự động tìm             |
| Sử dụng          | `source dacn-openrc.sh`              | `mgr.get_active_profile()` |
| Validation       | ❌ Không có                          | ✅ Có validate JSON        |

---

## 🐛 Troubleshooting

### Lỗi: "Config not found"

```bash
# Kiểm tra file có tồn tại không
ls -la openstack_config.json

# Tạo mới nếu chưa có
python3 openstack_config_manager.py setup
```

### Lỗi: "No active profile"

```bash
# Xem danh sách profiles
python3 openstack_config_manager.py list

# Switch sang profile khác
python3 openstack_config_manager.py switch --profile default
```

### Lỗi: "openstacksdk not found"

```bash
pip3 install openstacksdk
```

---

## 📖 Tài Liệu Liên Quan

- [OPENSTACK_CONFIG.md](terraform-generator/OPENSTACK_CONFIG.md) - Chi tiết kỹ thuật
- [SECURITY.md](SECURITY.md) - Best practices bảo mật
- [README.md](README.md) - Hướng dẫn chung

---

## ✅ Quick Start (TL;DR)

```bash
# 1. Setup
cd terraform-generator
python3 openstack_config_manager.py setup

# 2. Discover resources
python3 openstack_config_manager.py discover

# 3. Generate Terraform
python3 generate.py openstack 1

# ✅ Done! Credentials tự động load từ config
```
