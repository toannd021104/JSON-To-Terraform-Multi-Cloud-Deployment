# Tổng quan dự án: JSON-To-Terraform Multi-Cloud Deployment

Tài liệu này giải thích toàn bộ dự án theo cấu trúc module hiện tại, bao gồm chức năng từng thư mục, từng file quan trọng, luồng hoạt động và cách sử dụng. Nội dung được viết chi tiết để bạn có thể đọc và hiểu toàn bộ pipeline mà không cần mở từng file nguồn ngay lập tức.

---

## 1. Mục tiêu và phạm vi

Dự án cung cấp một pipeline tự động chuyển đổi topology JSON (mô tả hạ tầng) thành Terraform cho nhiều cloud (AWS/OpenStack), đồng thời xử lý user-data (cloud-init/cloudbase-init). Các mục tiêu chính:

- Chuẩn hóa mô tả hạ tầng độc lập với provider.
- Bắt lỗi sớm (schema + logic mạng + user-data).
- Sinh Terraform sẵn sàng `apply`.
- Hỗ trợ nhân bản hạ tầng (multi-copy) với suffix để tránh trùng.
- Tùy chọn AI để sửa topology hoặc review user-data.

Ngoài phạm vi:

- Vận hành runtime (monitoring, scaling, day-2 ops) chưa nằm trong scope.

---

## 2. Luồng hoạt động tổng quát

Luồng chuẩn khi chạy generator:

1) Đọc topology JSON (mặc định `generate/topology.json`).
2) Validate topology: schema + logic mạng.
3) Validate resource cloud (AMI/instance type hoặc image/flavor).
4) Xử lý user-data JSON → cloud-init YAML.
5) Sinh Terraform project theo provider.
6) (Tùy chọn) chạy terraform init/apply.

---

## 3. Cấu trúc thư mục

```
JSON-To-Terraform-Multi-Cloud-Deployment/
├─ validate/                  # Xác thực topology + user-data
├─ generate/                  # Tạo Terraform + cloud-init
├─ clone/                     # Nhân bản topology (multi-copy)
├─ providers/                 # Template Terraform cho AWS/OpenStack
├─ configs/                   # OpenStack config manager + docs
├─ templates/                 # Tài nguyên template hỗ trợ
├─ ai_generator/              # AI tạo topology.json
├─ evaluation/                # Framework đánh giá (nếu dùng)
└─ requirements.txt           # Dependency Python
```

---

## 4. Nhóm chức năng 1: Xác thực (validate/)

### 4.1. `validate/topology_schema.py`
**Vai trò**: Xác thực `topology.json` theo JSON schema + logic mạng.

**Các kiểm tra chính:**
- Schema: required fields, type, cấu trúc instances/networks/routers.
- IP hợp lệ và nằm trong CIDR.
- Không trùng IP trong cùng mạng.
- Network reference tồn tại (fuzzy matching typo).
- `gateway_ip` phải trùng router interface IP.
- Static routes có nexthop reachable.
- Cloud-init file tồn tại trong `generate/userdata/`.

**Input**: đường dẫn topology JSON.  
**Output**: `(is_valid: bool, errors: list)`.

---

### 4.2. `validate/cloud_resources_aws.py`
**Vai trò**: Kiểm tra tài nguyên AWS dựa trên topology.

**Chức năng:**
- Kiểm tra AMI hợp lệ theo region.
- Tìm instance type phù hợp theo CPU/RAM.

**Input**: topology dict.  
**Output**: danh sách instance đã map AMI + instance_type.

---

### 4.3. `validate/cloud_resources_openstack.py`
**Vai trò**: Kiểm tra image/flavor OpenStack.

**Chức năng:**
- Lấy danh sách image + flavor bằng OpenStack CLI.
- Match image name hoặc map flavor theo CPU/RAM/Disk.

**Input**: topology dict.  
**Output**: map instance → image + flavor (hoặc thông báo lỗi).

---

### 4.4. `validate/topology_ai_fixer.py`
**Vai trò**: Dùng Gemini để tự động sửa lỗi topology.

**Flow:**
1) Gửi topology + errors.
2) Nhận JSON đã sửa.
3) Hiển thị diff và confirm.

---

### 4.5. `validate/topology_ai_cross_check.py`
**Vai trò**: Sửa topology bằng OpenAI, kiểm tra lại bằng Gemini.

**Flow:**
- OpenAI fix → re-validate → Gemini review → chỉ apply nếu cả hai pass.

---

### 4.6. `validate/userdata_schema.py`
**Vai trò**: Schema validator cho user-data JSON.

**Chức năng:**
- Validate fields `files`, `users`, `packages`, `exec`, ...
- Tạo message lỗi chi tiết và gợi ý.

---

### 4.7. `validate/userdata_ai_review.py`
**Vai trò**: Review user-data bằng Gemini (semantic + security).

**Output**: JSON report (pass/warn/fail + suggested fixes).

---

## 5. Nhóm chức năng 2: Generate (generate/)

### 5.1. `generate/terraform_generator.py`
**Vai trò**: Orchestrator chính tạo Terraform từ topology.

**Flow chính:**
- Load OpenStack config (nếu provider = openstack).
- Validate topology.
- Validate resource cloud.
- Generate Terraform configs.
- Gọi terraform apply qua `run_terraform.py`.

**Input**: `python3 terraform_generator.py [aws|openstack] [copies]`.

---

### 5.2. `generate/terraform_templates.py`
**Vai trò**: Cung cấp template HCL cho AWS/OpenStack.

**Chức năng:**
- Block terraform/provider/locals.
- Module network/instance/security group.
- Shared VPC cho AWS.

---

### 5.3. `generate/cloudinit_generator.py`
**Vai trò**: Convert user-data JSON → cloud-init/cloudbase-init YAML.

**Quy trình:**
- Validate schema trước.
- Convert theo target OS (Linux/Windows).
- Output YAML chuẩn cloud-init.

---

### 5.4. `generate/cloudinit_processor.py`
**Vai trò**: Dùng trong Terraform generator để xử lý user-data.

**Chức năng:**
- Tìm user-data JSON trong `generate/userdata/`.
- Chạy `cloudinit_generator.py` để tạo YAML.
- Update `topology.json` trong output folder.

---

### 5.5. `generate/run_terraform.py`
**Vai trò**: Chạy terraform init/apply/destroy theo nhiều folder.

**Chức năng:**
- Parallel execution.
- Live log + bảng summary.
- Tự init trước khi apply/destroy.

---

### 5.6. `generate/userdata/`
**Vai trò**: Lưu JSON mẫu cho user-data.

Các file mẫu:
- `cloud_init.json`
- `cloudbase.json`
- `ubuntu-user.json`
- `schema.json`

---

### 5.7. `generate/scripts/`
**Vai trò**: Script tiện ích.

- `cleanup_all_openstack_resources_via_manager.sh`: xóa sạch OpenStack resources.
- `destroy_all_terraform_projects.sh`: destroy tất cả project.
- `verify_cloud_init.sh`: kiểm tra file cloud-init đã generate.

---

## 6. Nhóm chức năng 3: Clone (clone/)

### 6.1. `clone/topology_cloner.py`
**Vai trò**: Chứa logic nhân bản topology (multi-copy).

**Chức năng chính:**
- `modify_topology`: suffix hóa tên resource.
- `collect_all_networks_and_routers`: gom networks/routers cho multi-copy.
- `calculate_vpc_cidr`: tự tính VPC CIDR cho AWS.

---

## 7. Providers (providers/)

### 7.1. AWS
- `providers/aws/main.tf`, `variables.tf`, `outputs.tf`: template chính.
- Modules:
  - `modules/network`: VPC/subnet/route table/NAT.
  - `modules/security_groups`: SG mặc định + SG theo topology.
  - `modules/instance`: EC2 + EIP.
  - `modules/keypair`: SSH key.

### 7.2. OpenStack
- `providers/openstack/main.tf`, `variables.tf`: template chính.
- Modules:
  - `modules/network`: network/subnet/router/route.
  - `modules/instance`: VM + floating IP.
  - `modules/security_group`: SG default.
  - `modules/keypair`: SSH key.

---

## 8. Configs (configs/)

### 8.1. `configs/openstack_config_manager.py`
**Vai trò**: Quản lý credentials OpenStack (multi-profile).

**Các lệnh:**
- `setup`: tạo profile.
- `list`: xem profiles.
- `switch`: đổi active profile.
- `discover`: auto-discover external network.
- `export`: xuất terraform.tfvars.

### 8.2. `configs/OPENSTACK_CONFIG.md`
**Vai trò**: tài liệu chi tiết về OpenStack config manager.

---

## 9. Templates (templates/)

### 9.1. `templates/pre-template/order-minimal.cfg`
**Vai trò**: template cấu hình thứ tự modules cho cloud-init.

---

## 10. AI Topology Generator (ai_generator/)

### 10.1. `ai_generator/topology_generator.py`
**Vai trò**: Dùng Gemini để sinh topology.json dựa trên mô tả.

**Lệnh mẫu:**
```
python3 ai_generator/topology_generator.py interactive
```

---

## 11. Evaluation (evaluation/)

Framework đánh giá tự động theo 4 layer:

- **Layer A**: Input validation.
- **Layer B**: Terraform plan/apply.
- **Layer C**: Consistency topology vs state.
- **Layer D**: SSH kiểm tra user-data.

Entry point: `evaluation/evaluator.py`.

---

## 12. Cách sử dụng nhanh

### 12.1. Tạo hạ tầng OpenStack
```
cd generate
python3 terraform_generator.py openstack 1
```

### 12.2. Tạo hạ tầng AWS
```
cd generate
python3 terraform_generator.py aws 1
```

### 12.3. Dùng AI tạo topology
```
python3 ai_generator/topology_generator.py interactive
```

---

## 13. Lưu ý vận hành

- Với OpenStack, cần cấu hình `configs/openstack_config.json` hoặc chạy `configs/openstack_config_manager.py setup`.
- Với AWS, cần cấu hình AWS CLI + quyền EC2/VPC.
- Các file user-data phải nằm trong `generate/userdata/`.
- Terraform output sẽ nằm trong `terraform-projects/`.

---

## 14. Tóm tắt

Dự án được chia thành 3 khối chính:

- **validate/**: kiểm tra topology + user-data.  
- **generate/**: tạo Terraform + cloud-init.  
- **clone/**: nhân bản hạ tầng.  

Phần providers, configs, templates và ai_generator là các khối hỗ trợ để triển khai đầy đủ pipeline.

Nếu bạn muốn bổ sung thêm ví dụ chi tiết cho từng provider hoặc luồng AI, mình có thể mở rộng thêm.
