import json
import uuid
import sys
import os
import shutil
from pathlib import Path
from validate_json import validate_topology_file
from datetime import datetime


class TerraformGenerator:
    def __init__(self, provider, num_copies=1):
        self.provider = provider.lower()
        self.num_copies = num_copies
        self.topology = None
        self.validated_resources = None
        self.run()

    def run(self):
        print(f"\n=== Bắt đầu tạo file cho {self.provider.upper()} ===")
        if not self.load_and_validate_topology():
            sys.exit(1)
        self.validate_resources()
        self.generate_configs()
        print("\n=== ĐÃ HOÀN TẤT ===")

    def load_and_validate_topology(self) -> bool:
        """Tải và validate topology file"""
        print("\nĐang kiểm tra topology.json...")
        
        is_valid, errors = validate_topology_file("topology.json")
        
        if not is_valid:
            print("\n=== LỖI VALIDATION ===")
            for error in errors:
                print(f"- {error}")
            return False
        
        # Load file nếu validation thành công
        try:
            with open("topology.json", "r") as f:
                self.topology = json.load(f)
            print("Topology file hợp lệ")
            return True
        except Exception as e:
            print(f"\nLỗi khi đọc file: {str(e)}")
            return False
        
    def validate_resources(self):
        """Kiểm tra resources bằng các utility và lưu kết quả"""
        if self.provider == "openstack":
            try:
                from validate_openstack import validate_resources
                self.validated_resources = validate_resources(self.topology)
                
                print("\n=== KIỂM TRA RESOURCES THÀNH CÔNG ===")
                for instance in self.validated_resources['instances']:
                    print(f"\n[INSTANCE] {instance['name']}")
                    if 'image' in instance:
                        print(f"  Image: {instance['image']}")
                    if 'flavor' in instance:
                        print(f"  Flavor: {instance['flavor']}")
            except ImportError:
                self.exit_with_error("[LỖI] Không tìm thấy module openstack_utils")
                
        elif self.provider == "aws":
            try:
                from validate_aws import AWSUtils
                validate_aws = AWSUtils()
                self.validated_resources = validate_aws.validate_resources(self.topology)
                
                print("\n=== KIỂM TRA RESOURCES THÀNH CÔNG ===")
                for instance in self.validated_resources['instances']:
                    print(f"\n[INSTANCE] {instance['name']}")
                    if 'ami' in instance:
                        print(f"  AMI: {instance['ami']}")
                    if 'instance_type' in instance:
                        print(f"  Instance Type: {instance['instance_type']}")
            except ImportError:
                self.exit_with_error("[LỖI] Không tìm thấy module validate_aws")

    def exit_with_error(self, message):
        """Hàm trợ giúp để thoát với thông báo lỗi"""
        print(message)
        sys.exit(1)

    def terraform_block(self):
        """Khai báo phiên bản Terraform và provider"""
        if self.provider == "openstack":
            return """terraform {
        required_version = ">= 0.14.0"
        required_providers {
            openstack = {
            source  = "terraform-provider-openstack/openstack"
            version = "~> 1.53.0"
            }
        }
        }"""
        elif self.provider == "aws":
            return """terraform {
        required_version = ">= 0.14.0"
        
        required_providers {
            aws = {
            source  = "hashicorp/aws"
            version = "~> 4.0"
            }
        }
        }"""

    def provider_block(self):
        """Cấu hình provider"""
        if self.provider == "openstack":
            return """provider "openstack" {
        auth_url    = var.openstack_auth_url
        region      = var.openstack_region
        user_name   = var.openstack_user_name
        tenant_name = var.openstack_tenant_name
        password    = var.openstack_password
        endpoint_overrides = {
            compute = "http://10.102.192.230:8774/v2.1/"  
        }
        }"""
        elif self.provider == "aws":
            return """provider "aws" {
        region = var.aws_region
        }"""

    def locals_block(self):
        """Đọc file topology.json và tạo biến local"""
        if self.provider == "openstack":
            return """locals {
        topology = jsondecode(file("topology.json"))
        }"""
        elif self.provider == "aws":
            return """locals {
        topology     = jsondecode(file("topology.json"))
        networks_map = { for net in local.topology.networks : net.name => net }
        }"""

    def network_module(self):
        """Tạo module network"""
        if self.provider == "openstack":
            return """module "network" {
        source = "./modules/network"

        networks           = local.topology.networks
        routers            = local.topology.routers
        external_network_id = var.external_network_id
        }"""
        elif self.provider == "aws":
            return """module "network" {
        source = "./modules/network"

        vpc_cidr_block     = var.vpc_cidr_block
        public_subnet_cidrs = var.public_subnet_cidrs
        private_subnets    = local.topology.networks
        availability_zones = var.availability_zones
        routers            = local.topology.routers
        }"""

    def instance_module(self):
        """Tạo module instance từ kết quả đã kiểm tra"""
        if self.provider == "openstack":
            return self._openstack_instance_module()
        return self._aws_instance_module()

    def _openstack_instance_module(self, suffix=""):
        if not self.validated_resources or 'instances' not in self.validated_resources:
            self.exit_with_error("[LỖI] Không có dữ liệu resources đã validate")
        
        # Tạo map với tên instance đầy đủ (có suffix)
        validated_map = {}
        for inst in self.validated_resources['instances']:
            original_name = inst['original_spec']['name']
            full_name = f"{original_name}_{suffix}" if suffix else original_name
            validated_map[full_name] = {
                "image": inst['image'],
                "flavor": inst['flavor']
            }
        
        instance_config = f"""module "instance" {{
        depends_on = [module.network]
        source = "./modules/instance"
        
        for_each = {{ for inst in local.topology.instances : inst.name => inst }}

        instance_name = each.value.name
        image_name    = lookup({json.dumps(validated_map)}, each.key, {{}}).image
        flavor_name   = lookup({json.dumps(validated_map)}, each.key, {{}}).flavor
        network_id    = module.network.network_ids[each.value.networks[0].name]
        fixed_ip      = each.value.networks[0].ip
        user_data = each.value.cloud_init != null ? file("${{path.module}}/cloud_init/${{each.value.cloud_init}}") : null
        }}"""
        return instance_config

    def _aws_instance_module(self, suffix=""):
        """Generate AWS instance module using for_each with only ami and instance_type"""
        if not self.validated_resources or 'instances' not in self.validated_resources:
            self.exit_with_error("[LỖI] Không có dữ liệu resources đã validate")
        
        # Tạo map với tên instance đầy đủ (đã thêm suffix)
        validated_map = {}
        for inst in self.validated_resources['instances']:
            original_name = inst['original_spec']['name']  # Lấy tên gốc trước khi thêm suffix
            full_name = f"{original_name}_{suffix}" if suffix else original_name
            validated_map[full_name] = {
                "ami": inst['ami'],
                "instance_type": inst['instance_type']
            }
        
        instance_config = f"""module "instance" {{
            depends_on = [module.network]
            source = "./modules/instance"

            for_each = {{ for inst in local.topology.instances : inst.name => inst }}

            instance_name = each.value.name
            ami_id        = lookup({json.dumps(validated_map)}, each.key, {{}}).ami
            instance_type = lookup({json.dumps(validated_map)}, each.key, {{}}).instance_type
            subnet_id     = module.network.private_subnet_ids[each.value.networks[0].name]
            fixed_ip      = each.value.networks[0].ip
            user_data = each.value.cloud_init != null ? file("${{path.module}}/cloud_init/${{each.value.cloud_init}}") : null
            key_name = aws_key_pair.my_key.key_name
            security_group_ssh_ids = [aws_security_group.ssh_access.id]
        }}"""
        return instance_config

    def output_section(self):
        """Tạo output cho Terraform"""
        return """output "instance_ips" {
        value = {
            for k, v in module.instance : k => v.private_ip
        }
        }"""

    def generate_config_content(self):
        """Tạo nội dung file main.tf"""
        return f"""# Auto-generated Terraform configuration for {self.provider.upper()}
        {self.terraform_block()}

        {self.provider_block()}

        {self.locals_block()}

        {self.network_module()}

        {self.instance_module()}

        {self.output_section()}
        """

    def generate_configs(self):
        """Tạo các thư mục với topology.json đã chỉnh sửa"""
        # Đọc topology.json từ thư mục gốc
        with open('topology.json', 'r') as f:
            original_topology = json.load(f)
        
        # Tạo thư mục chính
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # Format: YYYYMMDD_HHMMSS
        main_folder = f"{self.provider}_{timestamp}"
        main_folder = os.path.join("../terraform-projects", main_folder)
        os.makedirs(main_folder, exist_ok=True)
        
        # Copy file run_terraform.py vào thư mục chính nếu nó tồn tại
        if os.path.exists("run_terraform.py"):
            shutil.copy("run_terraform.py", os.path.join(main_folder, "run_terraform.py"))
            print(f" Đã copy run_terraform.py vào {main_folder}")
        else:
            print(" [CẢNH BÁO] Không tìm thấy file run_terraform.py")
        
        # Tạo các thư mục con
        for i in range(self.num_copies):
            # Tạo suffix ngẫu nhiên 6 ký tự
            suffix = str(uuid.uuid4())[:6]
            dir_name = f"{self.provider}_{suffix}"
            full_path = os.path.join(main_folder, dir_name)
            
            # Tạo thư mục con trong thư mục chính
            self.create_provider_directory(full_path, original_topology, suffix)

    def create_provider_directory(self, dir_path, original_topology, suffix):
        try:
            # 1. Copy thư mục template
            shutil.copytree(self.provider, dir_path)
            
            # 2. Tạo topology.json mới với suffix
            modified_topology = self.modify_topology(original_topology, suffix)
            with open(os.path.join(dir_path, 'topology.json'), 'w') as f:
                json.dump(modified_topology, f, indent=2)
            
            # 3. Tạo main.tf với các tham số đã được cập nhật suffix
            config_content = f"""# Config tự động - Phiên bản {suffix}
        {self.terraform_block()}

        {self.provider_block()}

        locals {{
        topology = jsondecode(file("${{path.module}}/topology.json"))
        }}

        {self.network_module()}

        {self._openstack_instance_module(suffix) if self.provider == "openstack" else self._aws_instance_module(suffix)}

        {self.output_section()}
    """
            with open(os.path.join(dir_path, 'main.tf'), 'w', encoding='utf-8') as f:
                f.write(config_content)
            
            print(f" Đã tạo thành công: {dir_path}")
        
        except Exception as e:
            print(f" Lỗi khi tạo {dir_path}: {str(e)}")
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)

    def modify_topology(self, topology, suffix):
        """Thêm suffix vào tên các resource"""
        modified = json.loads(json.dumps(topology))  
        
        # Sửa tên instances
        for instance in modified.get('instances', []):
            instance['name'] = f"{instance['name']}_{suffix}"
            for net in instance.get('networks', []):
                net['name'] = f"{net['name']}_{suffix}"
        
        # Sửa tên networks
        for network in modified.get('networks', []):
            network['name'] = f"{network['name']}_{suffix}"
        
        # Sửa tên routers
        for router in modified.get('routers', []):
            router['name'] = f"{router['name']}_{suffix}"
            for net in router.get('networks', []):
                net['name'] = f"{net['name']}_{suffix}"
        
        return modified

if __name__ == "__main__":
    print("""
    ========================
    TERRAFORM CONFIG GENERATOR
    ========================""")
    
    # Cập nhật phần xử lý tham số dòng lệnh
    if len(sys.argv) < 2 or sys.argv[1].lower() not in ["aws", "openstack"]:
        print("\n[LỖI] Cách dùng: python generate.py [aws|openstack] [số_bản_sao]")
        sys.exit(1)
        
    provider = sys.argv[1].lower()
    num_copies = 1  # Mặc định là 1 bản
    
    # Xử lý tham số số lượng bản sao nếu có
    if len(sys.argv) > 2:
        try:
            num_copies = int(sys.argv[2])
            if num_copies < 1:
                raise ValueError
        except ValueError:
            print("\n[LỖI] Số bản sao phải là số nguyên dương")
            sys.exit(1)
    
    try:
        # Truyền thêm tham số num_copies khi khởi tạo
        TerraformGenerator(provider, num_copies)
    except KeyboardInterrupt:
        print("\n=== ĐÃ DỪNG CHƯƠNG TRÌNH ===")
    except Exception as e:
        print(f"\n=== LỖI KHÔNG MONG MUỐN ===\n{str(e)}")
        sys.exit(1)