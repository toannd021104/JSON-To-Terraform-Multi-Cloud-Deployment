# BÁO CÁO THỰC NGHIỆM ĐÁNH GIÁ HỆ THỐNG

## Chương: Thực nghiệm và Đánh giá

---

## 1. Giới thiệu

Chương này trình bày phương pháp đánh giá hệ thống sinh mã Terraform tự động từ mô tả JSON. Thực nghiệm được thiết kế theo mô hình **4 tầng đánh giá (4-Layer Evaluation)** nhằm kiểm chứng tính đúng đắn từ đầu vào đến đầu ra cuối cùng của hệ thống.

---

## 2. Mô hình đánh giá 4 tầng

### 2.1 Tổng quan kiến trúc đánh giá

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MÔ HÌNH ĐÁNH GIÁ 4 TẦNG                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐        │
│  │  Topology    │     │  Topology    │     │  Topology    │        │
│  │    tn1a      │     │ tn1b-2router │     │    tn1c      │        │
│  │  (Đơn giản)  │     │  (Trung bình)│     │  (Phức tạp)  │        │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘        │
│         │                    │                    │                 │
│         ▼                    ▼                    ▼                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              LAYER A: INPUT VALIDATION                       │   │
│  │         Kiểm tra tính hợp lệ của dữ liệu đầu vào            │   │
│  │    • Schema Validation (JSON Schema)                         │   │
│  │    • Logic Validation (Ràng buộc nghiệp vụ)                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              LAYER B: TERRAFORM DEPLOYMENT                   │   │
│  │           Kiểm tra khả năng triển khai thực tế              │   │
│  │    • Terraform Init/Plan/Apply                               │   │
│  │    • Resource Count, Duration, Success Rate                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              LAYER C: MODEL CONSISTENCY                      │   │
│  │      So sánh mô hình JSON với hạ tầng thực tế               │   │
│  │    • Networks: CIDR matching                                 │   │
│  │    • Instances: Name + Network mapping                       │   │
│  │    • Routers: External gateway + Interfaces                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              LAYER D: USER-DATA VERIFICATION                 │   │
│  │           Kiểm tra cấu hình cloud-init                       │   │
│  │    • Cloud-init file existence                               │   │
│  │    • Configuration checklist validation                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Chi tiết từng tầng đánh giá

#### **Layer A: Input Validation (Kiểm tra đầu vào)**

**Mục đích:** Đảm bảo file JSON topology tuân thủ đúng schema và các ràng buộc logic.

**Phương pháp kiểm tra:**

| Loại kiểm tra     | Mô tả                                   | Tiêu chí                                                   |
| ----------------- | --------------------------------------- | ---------------------------------------------------------- |
| Schema Validation | Kiểm tra cấu trúc JSON theo JSON Schema | Tất cả trường bắt buộc phải có, kiểu dữ liệu đúng          |
| Logic Validation  | Kiểm tra ràng buộc nghiệp vụ            | CIDR hợp lệ, tham chiếu network tồn tại, IP trong dải CIDR |

**Các ràng buộc logic được kiểm tra:**

- Mỗi instance phải tham chiếu đến network đã định nghĩa
- Gateway IP phải nằm trong dải CIDR của subnet
- Router interface phải tham chiếu đến network tồn tại
- Không có tên trùng lặp trong cùng loại resource

---

#### **Layer B: Terraform Deployment (Triển khai hạ tầng)**

**Mục đích:** Kiểm tra khả năng sinh mã Terraform và triển khai thành công lên cloud.

**Quy trình:**

```
JSON Topology → Terraform Generator → main.tf, variables.tf
                                           │
                                           ▼
                                    Terraform Init
                                           │
                                           ▼
                                    Terraform Plan
                                           │
                                           ▼
                                    Terraform Apply
                                           │
                                           ▼
                                    Ghi nhận kết quả
```

**Các chỉ số đo lường:**

| Chỉ số                  | Mô tả                      | Đơn vị         |
| ----------------------- | -------------------------- | -------------- |
| Apply Status            | Trạng thái triển khai      | Success/Failed |
| Resource Count          | Số lượng resource được tạo | Số nguyên      |
| Duration                | Thời gian triển khai       | Giây (s)       |
| Added/Changed/Destroyed | Số resource thay đổi       | Số nguyên      |

---

#### **Layer C: Model Consistency (Nhất quán mô hình)**

**Mục đích:** So sánh mô hình JSON đầu vào với trạng thái thực tế của hạ tầng sau khi triển khai.

**Phương pháp:**

1. Đọc file `terraform.tfstate` để lấy trạng thái thực tế
2. So sánh từng loại resource với định nghĩa trong JSON

**Bảng so sánh chi tiết:**

| Resource  | Thuộc tính so sánh                 | Phương pháp matching                    |
| --------- | ---------------------------------- | --------------------------------------- |
| Networks  | CIDR block                         | Exact match by CIDR                     |
| Subnets   | CIDR, Network ID                   | CIDR-based matching                     |
| Instances | Name, Network attachment           | Name + Network reference                |
| Routers   | Name, External gateway, Interfaces | Name + gateway status + interface count |

**Công thức tính Match Rate:**

$$
\text{Match Rate} = \frac{\text{Số resource khớp}}{\text{Tổng số resource trong JSON}} \times 100\%
$$

---

#### **Layer D: User-Data Verification (Xác minh Cloud-init)**

**Mục đích:** Kiểm tra cấu hình cloud-init được áp dụng đúng cho các VM.

**Các hạng mục kiểm tra:**

| Hạng mục             | Mô tả                                               |
| -------------------- | --------------------------------------------------- |
| File existence       | File cloud-init.yaml tồn tại trong thư mục instance |
| Package installation | Các package được định nghĩa có trong cloud-init     |
| User configuration   | Cấu hình user (SSH key, password)                   |
| Run commands         | Các lệnh khởi tạo                                   |
| Write files          | Các file được tạo                                   |

---

## 3. Ba kịch bản thực nghiệm

### 3.1 Tổng quan các kịch bản

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        BA KỊCH BẢN THỰC NGHIỆM                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  KỊCH BẢN 1: topology-tn1a (Đơn giản)                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                     │   │
│  │     ┌──────┐         ┌─────────────┐         ┌──────┐              │   │
│  │     │ PC1  │─────────│   web-net   │─────────│ PC2  │              │   │
│  │     └──────┘         │192.168.10.0 │         └──────┘              │   │
│  │                      └──────┬──────┘                               │   │
│  │                             │                                       │   │
│  │                      ┌──────┴──────┐                               │   │
│  │                      │ edge-router │────── Internet                │   │
│  │                      └─────────────┘                               │   │
│  │                                                                     │   │
│  │  • 2 Instances, 1 Network, 1 Router                                │   │
│  │  • Mô hình mạng đơn giản, 1 lớp                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  KỊCH BẢN 2: topology-tn1b-2router (Trung bình)                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                     │   │
│  │  ┌───────────┐      ┌─────────────┐      ┌───────────────┐         │   │
│  │  │ pc-center │──────│  core-net   │──────│  core-router  │── Internet│   │
│  │  └───────────┘      │192.168.20.0 │      └───────┬───────┘         │   │
│  │                     └─────────────┘              │                  │   │
│  │                                           ┌──────┴──────┐           │   │
│  │                                           │ transit-net │           │   │
│  │                                           │  10.0.0.0   │           │   │
│  │                                           └──────┬──────┘           │   │
│  │  ┌──────────┐       ┌─────────────┐      ┌───────┴───────┐         │   │
│  │  │ pc-right │───────│ access-net  │──────│ access-router │         │   │
│  │  └──────────┘       │192.168.30.0 │      └───────────────┘         │   │
│  │                     └─────────────┘                                │   │
│  │                                                                     │   │
│  │  • 2 Instances, 3 Networks (1 transit), 2 Routers                  │   │
│  │  • Mô hình mạng 2 tầng với transit network                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  KỊCH BẢN 3: topology-tn1c (Phức tạp)                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                     │   │
│  │        ┌───────────────┐           ┌───────────────┐               │   │
│  │        │ core-router-1 │───────────│ core-router-2 │               │   │
│  │        └───────┬───────┘           └───────┬───────┘               │   │
│  │                │                           │                        │   │
│  │       ┌────────┴────────┐         ┌────────┴────────┐              │   │
│  │       │  transit nets   │         │  transit nets   │              │   │
│  │       └────────┬────────┘         └────────┬────────┘              │   │
│  │                │                           │                        │   │
│  │        ┌───────┴───────┐           ┌───────┴───────┐               │   │
│  │        │ dist-router-1 │───────────│ dist-router-2 │               │   │
│  │        └───────┬───────┘           └───────┬───────┘               │   │
│  │                │                           │                        │   │
│  │    ┌───────────┴───────────┐   ┌───────────┴───────────┐           │   │
│  │    │                       │   │                       │           │   │
│  │ ┌──┴──┐  ┌──────┐     ┌──┴──┐  ┌──────┐              │           │
│  │ │ PC1 │  │ PC2  │     │ PC3 │  │ PC4  │              │           │
│  │ └─────┘  └──────┘     └─────┘  └──────┘              │           │
│  │                                                                     │   │
│  │  • 4 Instances, 9 Networks (5 transit), 4 Routers                  │   │
│  │  • Mô hình mạng 3 tầng: Core - Distribution - Access              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Chi tiết từng kịch bản

#### **Kịch bản 1: topology-tn1a (Mạng đơn giản)**

| Thành phần       | Số lượng | Chi tiết                          |
| ---------------- | -------- | --------------------------------- |
| Instances        | 2        | pc1, pc2                          |
| Networks         | 1        | web-net (192.168.10.0/24)         |
| Routers          | 1        | edge-router (có external gateway) |
| Transit Networks | 0        | -                                 |

**Đặc điểm:**

- Mô hình mạng phẳng, tất cả VM cùng subnet
- Một router duy nhất kết nối ra Internet
- Phù hợp cho ứng dụng đơn giản, không yêu cầu phân tách mạng

**Mục đích kiểm tra:**

- Khả năng xử lý topology cơ bản
- Tính đúng đắn của việc sinh cấu hình đơn giản

---

#### **Kịch bản 2: topology-tn1b-2router (Mạng 2 tầng)**

| Thành phần       | Số lượng | Chi tiết                                 |
| ---------------- | -------- | ---------------------------------------- |
| Instances        | 2        | pc-center, pc-right                      |
| Networks         | 3        | core-net, access-net, transit-net        |
| Routers          | 2        | core-router, access-router               |
| Transit Networks | 1        | transit-net (10.0.0.0/30) - gateway null |

**Đặc điểm:**

- Mô hình mạng 2 tầng với transit network
- Transit network không có gateway (dùng cho kết nối router-to-router)
- Chỉ core-router có external gateway

**Mục đích kiểm tra:**

- Khả năng xử lý multi-router topology
- Xử lý transit network (gateway = null)
- Định tuyến giữa các subnet khác nhau

---

#### **Kịch bản 3: topology-tn1c (Mạng 3 tầng Core-Distribution-Access)**

| Thành phần       | Số lượng | Chi tiết                     |
| ---------------- | -------- | ---------------------------- |
| Instances        | 4        | pc1, pc2, pc3, pc4           |
| Networks         | 9        | 4 access-net, 5 transit-net  |
| Routers          | 4        | 2 core-router, 2 dist-router |
| Transit Networks | 5        | Kết nối giữa các tầng        |

**Đặc điểm:**

- Mô hình mạng 3 tầng theo kiến trúc enterprise
- Nhiều transit network cho kết nối inter-router
- Có redundancy ở tầng core và distribution
- Access network cho từng nhóm VM

**Mục đích kiểm tra:**

- Khả năng xử lý topology phức tạp
- Xử lý nhiều transit network
- Tính mở rộng của hệ thống

---

## 4. Kết quả thực nghiệm

### 4.1 Bảng kết quả tổng hợp

| Layer        | Topology tn1a                | Topology tn1b-2router         | Topology tn1c                 |
| ------------ | ---------------------------- | ----------------------------- | ----------------------------- |
| **Layer A**  | ✓ PASS (21 schema, 7 logic)  | ✓ PASS (30 schema, 13 logic)  | ✓ PASS (66 schema, 35 logic)  |
| **Layer B**  | ✓ SUCCESS (9 resources, 49s) | ✓ SUCCESS (22 resources, 52s) | ✓ SUCCESS (68 resources, 75s) |
| **Layer C**  | ✓ 100% Match                 | ✓ 100% Match                  | ✓ 100% Match                  |
| **Layer D**  | ✓ 2/2 VMs                    | ✓ 2/2 VMs                     | ✓ 4/4 VMs                     |
| **Tổng kết** | **4/4 PASSED**               | **4/4 PASSED**                | **4/4 PASSED**                |

### 4.2 Phân tích chi tiết

#### Layer A - Input Validation

```
Số kiểm tra Schema theo độ phức tạp:
┌────────────────────┬────────┬────────┬────────┐
│ Topology           │ Schema │ Logic  │ Tổng   │
├────────────────────┼────────┼────────┼────────┤
│ tn1a               │   21   │    7   │   28   │
│ tn1b-2router       │   30   │   13   │   43   │
│ tn1c               │   66   │   35   │  101   │
└────────────────────┴────────┴────────┴────────┘
```

**Nhận xét:** Số lượng kiểm tra tăng tuyến tính theo độ phức tạp của topology, chứng tỏ hệ thống validation có khả năng mở rộng tốt.

#### Layer B - Terraform Deployment

```
Tương quan giữa độ phức tạp và thời gian triển khai:

Thời gian (s)
    80 │                              ●  tn1c
       │                           ╱
    60 │              ●  tn1b   ╱
       │           ╱          ╱
    40 │    ●  tn1a        ╱
       │    │           ╱
    20 │    │        ╱
       │    │     ╱
     0 └────┴────┴────┴────┴────┴────┴────┴────
           10   20   30   40   50   60   70   Resources
```

**Nhận xét:**

- Thời gian triển khai tỷ lệ thuận với số lượng resource
- Tốc độ trung bình: ~1 resource/giây

#### Layer C - Model Consistency

| Topology     | Networks | Instances | Routers | Match Rate |
| ------------ | -------- | --------- | ------- | ---------- |
| tn1a         | 1/1      | 2/2       | 1/1     | 100%       |
| tn1b-2router | 3/3      | 2/2       | 2/2     | 100%       |
| tn1c         | 9/9      | 4/4       | 4/4     | 100%       |

**Phương pháp so sánh đặc biệt:**

- **Networks:** So sánh bằng CIDR thay vì tên (do OpenStack subnet name có thể rỗng)
- **Instances:** Mapping qua network_id để xác định network attachment
- **Routers:** Kiểm tra external gateway và số lượng interface

#### Layer D - User-Data Verification

| Topology     | VMs | Cloud-init Files | Checklist Items |
| ------------ | --- | ---------------- | --------------- |
| tn1a         | 2   | 2                | 8               |
| tn1b-2router | 2   | 2                | 8               |
| tn1c         | 4   | 4                | 16              |

---

## 5. Nguyên lý kiểm tra

### 5.1 Nguyên lý End-to-End Verification

```
                    NGUYÊN LÝ KIỂM TRA END-TO-END

     Input                Processing              Output
  ┌─────────┐          ┌─────────────┐         ┌─────────┐
  │  JSON   │  ─────►  │  Generator  │  ─────► │Terraform│
  │Topology │          │   System    │         │  State  │
  └────┬────┘          └─────────────┘         └────┬────┘
       │                                            │
       │              VERIFICATION                  │
       │         ┌───────────────────┐              │
       └────────►│  Layer A + C + D  │◄─────────────┘
                 │   Comparator      │
                 └───────────────────┘
                          │
                          ▼
                 ┌───────────────────┐
                 │  PASS / FAIL      │
                 └───────────────────┘
```

**Giải thích:**

- Kiểm tra từ đầu vào (Layer A) đến đầu ra cuối cùng (Layer C, D)
- Đảm bảo tính toàn vẹn của quá trình chuyển đổi
- Phát hiện lỗi ở mọi giai đoạn

### 5.2 Nguyên lý Tăng dần độ phức tạp (Incremental Complexity)

```
Độ phức tạp
     ▲
     │                           ┌─────────┐
  10 │                           │  tn1c   │
     │                           │ 4R, 9N  │
     │                           └─────────┘
   5 │           ┌─────────────┐
     │           │ tn1b-2router│
     │           │   2R, 3N    │
   1 │ ┌────────┐└─────────────┘
     │ │  tn1a  │
     │ │ 1R, 1N │
     └─┴────────┴─────────────────────────────►
       Kịch bản 1    Kịch bản 2    Kịch bản 3
```

**Giải thích:**

- Bắt đầu từ kịch bản đơn giản, tăng dần độ phức tạp
- Giúp xác định ngưỡng lỗi và khả năng mở rộng
- Đánh giá hiệu năng theo độ phức tạp

### 5.3 Nguyên lý Multi-Layer Isolation

Mỗi layer đánh giá một khía cạnh độc lập:

| Layer | Khía cạnh đánh giá      | Độc lập với   |
| ----- | ----------------------- | ------------- |
| A     | Tính đúng đắn của input | -             |
| B     | Khả năng triển khai     | Layer A       |
| C     | Tính nhất quán model    | Layer A, B    |
| D     | Cấu hình cloud-init     | Layer A, B, C |

**Lợi ích:**

- Dễ dàng xác định vị trí lỗi
- Có thể chạy độc lập từng layer
- Tái sử dụng kết quả giữa các lần chạy

---

## 6. Kết luận

### 6.1 Đánh giá hiệu quả hệ thống

| Tiêu chí             | Kết quả                          | Đánh giá       |
| -------------------- | -------------------------------- | -------------- |
| Tính đúng đắn        | 100% pass all layers             | Xuất sắc       |
| Khả năng mở rộng     | Xử lý được topology 68 resources | Tốt            |
| Thời gian triển khai | ~1 resource/giây                 | Chấp nhận được |
| Tính nhất quán       | 100% match rate                  | Xuất sắc       |

### 6.2 Những điểm nổi bật

1. **Mô hình 4 tầng đánh giá** cho phép kiểm tra toàn diện từ input đến output
2. **Ba kịch bản** với độ phức tạp tăng dần giúp đánh giá khả năng mở rộng
3. **So sánh CIDR-based** giải quyết vấn đề subnet name rỗng trong OpenStack
4. **Tự động hóa hoàn toàn** quy trình đánh giá

### 6.3 Hạn chế và hướng phát triển

| Hạn chế                 | Hướng phát triển                |
| ----------------------- | ------------------------------- |
| Chỉ test trên OpenStack | Mở rộng cho AWS, GCP, Azure     |
| Chưa có stress test     | Thêm kịch bản với hàng trăm VMs |
| Chưa test failover      | Thêm kiểm tra khả năng phục hồi |

---

## Phụ lục: Cấu trúc file kết quả

```
evaluation/results/comparative_YYYYMMDD_HHMMSS/
├── topology-tn1a/
│   ├── layer_a_result.json    # Kết quả validation
│   ├── layer_b_result.json    # Kết quả deployment
│   ├── layer_c_result.json    # Kết quả consistency
│   ├── layer_d_result.json    # Kết quả cloud-init
│   └── summary.json           # Tổng hợp
├── topology-tn1b-2router/
│   └── ...
├── topology-tn1c/
│   └── ...
└── comparison_report.json     # Báo cáo so sánh tổng hợp
```

---

_Ngày thực hiện: 26/12/2024_
_Hệ thống: JSON-To-Terraform-Multi-Cloud-Deployment_
_Cloud Provider: OpenStack_
