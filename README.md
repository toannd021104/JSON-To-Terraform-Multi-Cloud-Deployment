Dự án sử dụng AWS SSO để truy cập tài nguyên từ container. Làm theo các bước sau:
# Bước 1: Cấu hình SSO
aws configure sso --profile my-sso

# Bước 2: Đăng nhập SSO
aws sso login --profile my-sso

# Bước 3: Chạy backend
docker compose up --build

Để dùng Terraform với OpenStack, tạo file *.tfvars chứa thông tin đăng nhập tại:
/terraform-generator/openstack/

Để chạy frontend
cd frontend
npm install
npm start
