# JSON-To-Terraform: Luồng Hoạt Động (OpenStack)

## 📋 Tổng Quan

Dự án này tự động chuyển đổi file JSON mô tả hạ tầng (`topology.json`) thành Terraform configurations và deploy lên OpenStack.

```
topology.json → validate → generate .tf files → terraform apply → ☁️ OpenStack
```

---

## 🚀 Lệnh Chạy

```bash
cd terraform-generator
python3 generate.py openstack [số_bản_sao]
```

**Ví dụ:**

```bash
python3 generate.py openstack 1    # Tạo 1 bộ hạ tầng
python3 generate.py openstack 3    # Tạo 3 bộ hạ tầng giống nhau (multi-tenant)
```

---

## 📊 Sơ Đồ Luồng Xử Lý

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          python3 generate.py openstack 1                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 0: Load OpenStack Config                                               │
│  ─────────────────────────────                                               │
│  File: openstack_config_manager.py                                          │
│  Input:  openstack_config.json                                              │
│  Output: Credentials + Auto-discovered external network                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: Validate Topology                                                   │
│  ─────────────────────────────                                               │
│  File: validators/validate_json.py                                          │
│  Input:  topology.json                                                      │
│  Output: Valid/Invalid + Error messages                                     │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Nếu có lỗi và GEMINI_API_KEY được set:                              │   │
│  │  File: validators/ai_fixer.py                                        │   │
│  │  → AI tự động sửa lỗi topology.json                                  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: Validate Cloud Resources                                            │
│  ────────────────────────────────                                            │
│  File: validators/validate_openstack.py                                     │
│  Input:  topology.json (instances với image, cpu, ram, disk)                │
│  Output: Matched images và flavors từ OpenStack                             │
│                                                                              │
│  Ví dụ: image="ubuntu-jammy", cpu=2, ram=4G → flavor="m2"                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 3: Generate Terraform Configs                                         │
│  ──────────────────────────────────                                          │
│  Files: terraform_templates.py + cloud_init_processor.py                    │
│                                                                              │
│  Output folder: terraform-projects/openstack_YYYYMMDD_HHMMSS/               │
│     ├── run_terraform.py                                                    │
│     └── openstack_abc123/                                                   │
│           ├── main.tf          ← Generated từ templates                     │
│           ├── variables.tf     ← Updated với discovered config             │
│           ├── topology.json    ← Copy với suffix unique                    │
│           ├── cloud_init/      ← YAML files từ JSON                        │
│           └── modules/         ← Copy từ openstack/modules                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 4: Run Terraform Apply                                                 │
│  ───────────────────────────                                                 │
│  File: run_terraform.py                                                     │
│  Commands: terraform init → terraform apply -auto-approve                   │
│  Output: Resources được tạo trên OpenStack                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Chi Tiết Các File

### 1️⃣ `openstack_config_manager.py`

**Mục đích:** Quản lý credentials OpenStack tập trung

| Thuộc tính        | Mô tả                                                                  |
| ----------------- | ---------------------------------------------------------------------- |
| **Input**         | `openstack_config.json`                                                |
| **Output**        | Dict chứa `auth_url`, `username`, `password`, `project_name`, `region` |
| **Auto-discover** | External network (`public-network`), Service endpoints                 |

**Cách sử dụng:**

```python
from openstack_config_manager import OpenStackConfigManager
mgr = OpenStackConfigManager()
mgr.load_config()
profile = mgr.get_active_profile()  # {'auth_url': '...', 'username': '...', ...}
```

---

### 2️⃣ `validators/validate_json.py`

**Mục đích:** Validate `topology.json` theo schema và logic mạng

| Thuộc tính | Mô tả                                 |
| ---------- | ------------------------------------- |
| **Input**  | `topology.json`                       |
| **Output** | `(is_valid: bool, errors: List[str])` |

**Các loại validation:**

- ✅ JSON Schema (required fields, types)
- ✅ IP trong CIDR range
- ✅ Không trùng IP trong cùng network
- ✅ Network được reference phải tồn tại
- ✅ Gateway IP phải match với Router IP
- ✅ Static routes phải reachable

**Fuzzy matching:** Phát hiện typo (vd: `"tet-net"` → suggest `"test-net"`)

---

### 3️⃣ `validators/ai_fixer.py`

**Mục đích:** Dùng Gemini AI để tự động sửa lỗi topology

| Thuộc tính   | Mô tả                                 |
| ------------ | ------------------------------------- |
| **Input**    | Current topology + validation errors  |
| **Output**   | Fixed topology JSON                   |
| **Requires** | `GEMINI_API_KEY` environment variable |

**Flow:**

1. Gửi topology + errors cho Gemini
2. Nhận fixed JSON
3. Hiển thị diff preview
4. User confirm → Apply fix

---

### 4️⃣ `validators/validate_openstack.py`

**Mục đích:** Match instances với OpenStack images/flavors

| Thuộc tính | Mô tả                                                       |
| ---------- | ----------------------------------------------------------- |
| **Input**  | `topology.json` (instances)                                 |
| **Output** | `{valid: bool, instances: [{image, flavor}], messages: []}` |

**Logic matching:**

```
topology.json                    OpenStack
─────────────                    ─────────
image: "ubuntu-jammy"    →       Image ID/Name match
cpu: 2, ram: 4, disk: 20 →       Flavor "m2" (best fit)
```

---

### 5️⃣ `terraform_templates.py`

**Mục đích:** Generate Terraform code blocks

| Function                                  | Output                                             |
| ----------------------------------------- | -------------------------------------------------- |
| `os_terraform_block()`                    | Terraform version + provider requirements          |
| `os_provider_block()`                     | OpenStack provider với auth variables              |
| `os_locals_block()`                       | Load `topology.json` vào `local.topology`          |
| `os_network_module_block()`               | Module call cho networks/routers                   |
| `os_instance_module_block(validated_map)` | Module call cho instances với image/flavor mapping |

**Ví dụ output:**

```hcl
module "instance" {
  for_each = { for inst in local.topology.instances : inst.name => inst }
  image_name  = lookup({"vm1": {"image": "ubuntu-jammy", "flavor": "m2"}}, each.key, {}).image
  flavor_name = lookup(...).flavor
  ...
}
```

---

### 6️⃣ `cloud_init_processor.py`

**Mục đích:** Chuyển cloud-init JSON → YAML

| Thuộc tính | Mô tả                                      |
| ---------- | ------------------------------------------ |
| **Input**  | `cloud-init-generator/*.json`              |
| **Output** | `terraform-projects/.../cloud_init/*.yaml` |

**Flow:**

1. Đọc `cloud_init` field từ instance trong topology
2. Tìm file JSON trong `cloud-init-generator/`
3. Detect OS (linux/windows)
4. Gọi `generate_cloudinit.py` để convert → YAML
5. Save vào `cloud_init/` folder

---

### 7️⃣ `run_terraform.py`

**Mục đích:** Chạy Terraform commands song song

| Thuộc tính   | Mô tả                         |
| ------------ | ----------------------------- |
| **Commands** | `init`, `apply`, `destroy`    |
| **Parallel** | Chạy nhiều folder cùng lúc    |
| **Output**   | Live progress + Results table |

**Cách sử dụng:**

```bash
cd terraform-projects/openstack_YYYYMMDD_HHMMSS/
python3 run_terraform.py apply     # Deploy
python3 run_terraform.py destroy   # Cleanup
```

---

## 📂 Cấu Trúc Thư Mục

```
terraform-generator/
├── generate.py                    ← Entry point chính
├── openstack_config_manager.py    ← Quản lý credentials
├── openstack_config.json          ← Credentials (gitignored)
├── terraform_templates.py         ← Terraform code templates
├── cloud_init_processor.py        ← JSON → YAML converter
├── run_terraform.py               ← Terraform executor
├── topology.json                  ← Input: mô tả hạ tầng
│
├── validators/
│   ├── validate_json.py           ← Schema + network validation
│   ├── validate_openstack.py      ← Image/flavor matching
│   └── ai_fixer.py                ← AI auto-fix (Gemini)
│
├── openstack/                     ← Template folder (sẽ copy)
│   ├── main.tf
│   ├── variables.tf
│   └── modules/
│       ├── network/               ← Networks, routers, subnets
│       ├── instance/              ← VMs với floating IP
│       ├── keypair/               ← SSH keys
│       └── security_group/        ← Security groups
│
├── scripts/
│   ├── cleanup_all_resources.sh           ← Force delete OpenStack resources
│   └── destroy_all_terraform_projects.sh  ← Terraform destroy all projects
│
└── cloud-init-generator/          ← Cloud-init JSON templates
    ├── generate_cloudinit.py
    ├── schema.json
    └── *.json                     ← Config files
```

---

## 📝 Ví Dụ topology.json

```json
{
  "instances": [
    {
      "name": "web-server",
      "image": "ubuntu-jammy",
      "cpu": 2,
      "ram": 4,
      "disk": 20,
      "networks": [{ "name": "internal", "ip": "192.168.1.10" }],
      "keypair": "my-key",
      "security_groups": ["web-sg"],
      "floating_ip": true,
      "cloud_init": "web-config.json"
    }
  ],
  "networks": [
    {
      "name": "internal",
      "cidr": "192.168.1.0/24",
      "gateway_ip": "192.168.1.1",
      "enable_dhcp": true
    }
  ],
  "routers": [
    {
      "name": "edge-router",
      "external": true,
      "networks": [{ "name": "internal", "ip": "192.168.1.1" }]
    }
  ]
}
```

---

## 🔧 Scripts Hỗ Trợ

### Cleanup OpenStack Resources (Force)

```bash
./scripts/cleanup_all_resources.sh [iterations]
```

Xóa tất cả: instances → ports → routes → routers → networks

### Destroy All Terraform Projects

```bash
./scripts/destroy_all_terraform_projects.sh
```

Chạy `terraform destroy` cho tất cả projects trong `terraform-projects/`

---

## ⚡ Quick Start

```bash
# 1. Setup credentials
cd terraform-generator
python3 openstack_config_manager.py setup

# 2. Tạo/sửa topology.json theo nhu cầu

# 3. Generate và Deploy
python3 generate.py openstack 1

# 4. Cleanup khi xong
./scripts/destroy_all_terraform_projects.sh
```

---

## 🔐 Bảo Mật

Các file sau được gitignore tự động:

- `openstack_config.json` - Credentials
- `*.tfvars` - Terraform variables
- `terraform.tfstate*` - Terraform state

---

## 📖 Tài Liệu Liên Quan

- [OPENSTACK_CONFIG_GUIDE.md](OPENSTACK_CONFIG_GUIDE.md) - Hướng dẫn config manager
- [terraform-generator/OPENSTACK_CONFIG.md](terraform-generator/OPENSTACK_CONFIG.md) - Chi tiết kỹ thuật
- [SECURITY.md](SECURITY.md) - Best practices bảo mật
