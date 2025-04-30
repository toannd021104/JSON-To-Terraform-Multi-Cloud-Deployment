FROM python:3.9-slim

WORKDIR /app

# Cài đặt các công cụ cần thiết và Terraform
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
 && wget https://releases.hashicorp.com/terraform/1.5.7/terraform_1.5.7_linux_amd64.zip \
 && unzip terraform_1.5.7_linux_amd64.zip \
 && mv terraform /usr/local/bin/ \
 && rm terraform_1.5.7_linux_amd64.zip \
 && rm -rf /var/lib/apt/lists/*

# Copy source code
COPY . .

# Cài đặt thư viện Python cần thiết
RUN pip install fastapi uvicorn pydantic

# Chạy ứng dụng FastAPI
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]