#!/usr/bin/env python3
"""OpenStack Config Manager - Multi-profile management with auto-discovery

Quản lý credentials OpenStack tập trung, hỗ trợ nhiều profiles và tự động
phát hiện tài nguyên (external networks, service endpoints).

Sử dụng:
    python3 configs/openstack_config_manager.py setup    # Tạo profile mới
    python3 configs/openstack_config_manager.py list     # Xem danh sách profiles
    python3 configs/openstack_config_manager.py discover # Tự động tìm external network
    python3 configs/openstack_config_manager.py export   # Xuất ra terraform.tfvars
"""
import json, os, sys

# Kiểm tra openstacksdk có cài hay không (cần cho auto-discovery)
try:
    import openstack
    SDK = True
except ImportError:
    SDK = False

# Kiểm tra rich library (optional - chỉ để UI đẹp hơn)
try:
    from rich.console import Console
    from rich.prompt import Prompt
    from rich.table import Table
    from rich.panel import Panel
    console = Console()
    RICH = True
except ImportError:
    RICH = False
    console = None

def msg(text, color=""):
    """In text với màu (nếu có rich library) hoặc plain text
    
    Args:
        text: Nội dung cần in
        color: Màu (red, green, yellow, cyan, blue) - chỉ hoạt động nếu có rich
    """
    if RICH:
        console.print(f"[{color}]{text}[/{color}]" if color else text)
    else:
        print(text)

class OpenStackConfigManager:
    """Class quản lý config OpenStack từ file JSON
    
    Attributes:
        config_file: Đường dẫn đến file JSON (mặc định: openstack_config.json)
        config: Dictionary chứa tất cả profiles và settings
        active_profile: Tên profile đang được sử dụng
    """
    
    def __init__(self, config_file=None):
        # Luôn lấy file config ở cùng thư mục với script này
        if config_file is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            self.config_file = os.path.join(script_dir, "openstack_config.json")
        else:
            self.config_file = config_file
        self.config = None  # Sẽ load từ JSON file
        self.active_profile = None  # Profile hiện tại (e.g., 'default')
        
    def load_config(self):
        """Đọc config từ file JSON
        
        Returns:
            dict: Config data nếu thành công, None nếu thất bại
        """
        if not os.path.exists(self.config_file):
            return None
        try:
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
            # Lấy profile đang active (default nếu không có)
            self.active_profile = self.config.get('active_profile', 'default')
            return self.config
        except Exception as e:
            msg(f"Error: {e}", "red")
            return None
    
    def save_config(self):
        """Lưu config xuống file JSON
        
        Returns:
            bool: True nếu lưu thành công, False nếu lỗi
        """
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            msg(f"Error: {e}", "red")
            return False
    
    def create_default_config(self):
        self.config = {
            "profiles": {"default": {
                "auth_url": "", "region": "RegionOne", "project_name": "",
                "username": "", "password": "", 
                "user_domain_name": "Default", "project_domain_id": "default"
            }},
            "active_profile": "default"
        }
        self.save_config()
    
    def interactive_setup(self):
        if RICH:
            console.print(Panel.fit("[bold cyan]OpenStack Configuration Setup[/bold cyan]", border_style="cyan"))
            profile_name = Prompt.ask("[cyan]Profile name[/cyan]", default="default")
            auth_url = Prompt.ask("[cyan]Auth URL[/cyan]", default="http://localhost:5000")
            region = Prompt.ask("[cyan]Region[/cyan]", default="RegionOne")
            project_name = Prompt.ask("[cyan]Project Name[/cyan]")
            username = Prompt.ask("[cyan]Username[/cyan]")
            password = Prompt.ask("[cyan]Password[/cyan]", password=True)
        else:
            print("\n=== OpenStack Setup ===")
            profile_name = input("Profile [default]: ") or "default"
            auth_url = input("Auth URL [http://localhost:5000]: ") or "http://localhost:5000"
            region = input("Region [RegionOne]: ") or "RegionOne"
            project_name = input("Project: ")
            username = input("Username: ")
            password = input("Password: ")
        
        if not self.config:
            self.create_default_config()
        
        self.config['profiles'][profile_name] = {
            "auth_url": auth_url, "region": region, "project_name": project_name,
            "username": username, "password": password,
            "user_domain_name": "Default", "project_domain_id": "default"
        }
        self.config['active_profile'] = profile_name
        self.save_config()
        msg(f"\n✓ Profile '{profile_name}' created", "green")
        return True
    
    def list_profiles(self):
        if not self.config or 'profiles' not in self.config:
            msg("No profiles found", "yellow")
            return
        
        if RICH:
            table = Table(title="OpenStack Profiles")
            table.add_column("Profile", style="cyan")
            table.add_column("Auth URL", style="blue")
            table.add_column("Project", style="green")
            table.add_column("Active", style="yellow")
            for name, profile in self.config['profiles'].items():
                table.add_row(name, profile.get('auth_url', 'N/A'), 
                            profile.get('project_name', 'N/A'),
                            "✓" if name == self.config.get('active_profile') else "")
            console.print(table)
        else:
            print("\n=== Profiles ===")
            for name, profile in self.config['profiles'].items():
                active = "[ACTIVE]" if name == self.config.get('active_profile') else ""
                print(f"{name} {active}\n  URL: {profile.get('auth_url')}\n  Project: {profile.get('project_name')}")
    
    def switch_profile(self, profile_name):
        if not self.config or profile_name not in self.config.get('profiles', {}):
            msg(f"Profile '{profile_name}' not found", "red")
            return False
        self.config['active_profile'] = profile_name
        self.active_profile = profile_name
        self.save_config()
        msg(f"✓ Switched to '{profile_name}'", "green")
        return True
    
    def get_active_profile(self):
        """Lấy thông tin profile đang active
        
        Returns:
            dict: Profile data chứa auth_url, username, password, etc.
                  None nếu không có config hoặc profile không tồn tại
        
        Example:
            profile = mgr.get_active_profile()
            # {'auth_url': 'http://...', 'username': '...', 'password': '...'}
        """
        if not self.config:
            return None
        return self.config['profiles'].get(self.config.get('active_profile', 'default'))
    
    def discover_resources(self):
        """Tự động phát hiện tài nguyên OpenStack (external network, endpoints)
        
        Kết nối vào OpenStack dùng credentials từ active profile, sau đó:
        - Tìm external network đầu tiên (is_router_external=True)
        - Lấy danh sách public endpoints từ service catalog
        
        Returns:
            dict: {
                'external_network': {'id': '...', 'name': 'public-network'},
                'endpoints': {'compute': 'http://...', 'network': 'http://...'}
            }
            None nếu không có openstacksdk hoặc xảy ra lỗi
        """
        if not SDK:
            msg("Install openstacksdk: pip install openstacksdk", "yellow")
            return None
        
        profile = self.get_active_profile()
        if not profile:
            msg("No active profile", "red")
            return None
        
        try:
            # Kết nối vào OpenStack API
            conn = openstack.connect(
                auth_url=profile['auth_url'], project_name=profile['project_name'],
                username=profile['username'], password=profile['password'],
                region_name=profile['region'], user_domain_name=profile.get('user_domain_name', 'Default'),
                project_domain_id=profile.get('project_domain_id', 'default')
            )
            
            discovered = {}
            auto = self.config.get('auto_discover', {})
            
            # Tìm external network (mặc định: bật)
            if auto.get('external_network', True):
                nets = list(conn.network.networks(is_router_external=True))
                if nets:
                    discovered['external_network'] = {'id': nets[0].id, 'name': nets[0].name}
                    # Auto-update profile với external network name nếu chưa có
                    if 'external_network_name' not in profile:
                        profile['external_network_name'] = nets[0].name
                        self.config['profiles'][self.active_profile] = profile
                        self.save_config()
            
            # Lấy danh sách public endpoints từ service catalog (mặc định: bật)
            if auto.get('endpoints', True):
                discovered['endpoints'] = {}
                for svc in conn.service_catalog:
                    for ep in svc.get('endpoints', []):
                        if ep.get('interface') == 'public':
                            # Lưu endpoint theo service type (compute, network, image, etc.)
                            discovered['endpoints'][svc.get('type')] = ep.get('url')
            
            return discovered
        except Exception as e:
            msg(f"Discovery error: {e}", "red")
            return None
    
    def export_terraform_vars(self, output="terraform.tfvars"):
        profile = self.get_active_profile()
        if not profile:
            return False
        
        discovered = self.discover_resources()
        content = f"""# Auto-generated from profile: {self.active_profile}
openstack_auth_url    = "{profile['auth_url']}"
openstack_region      = "{profile['region']}"
openstack_tenant_name = "{profile['project_name']}"
openstack_user_name   = "{profile['username']}"
openstack_password    = "{profile['password']}"
"""
        if discovered and 'external_network' in discovered:
            net = discovered['external_network']
            content += f'\nexternal_network_id   = "{net["id"]}"\nexternal_network_name = "{net["name"]}"\n'
        
        try:
            with open(output, 'w') as f:
                f.write(content)
            msg(f"✓ Exported to {output}", "green")
            return True
        except Exception as e:
            msg(f"Export error: {e}", "red")
            return False

if __name__ == '__main__':
    import argparse
    import subprocess
    
    # Kiểm tra nếu có 'openstack' command - pass-through mode
    if len(sys.argv) > 1 and sys.argv[1] == 'openstack':
        mgr = OpenStackConfigManager()
        mgr.load_config()
        profile = mgr.get_active_profile()
        
        if not profile:
            msg("No active profile found", "red")
            sys.exit(1)
        
        # Set environment variables
        env = os.environ.copy()
        env['OS_AUTH_URL'] = profile['auth_url']
        env['OS_PROJECT_NAME'] = profile['project_name']
        env['OS_USERNAME'] = profile['username']
        env['OS_PASSWORD'] = profile['password']
        env['OS_REGION_NAME'] = profile['region']
        env['OS_USER_DOMAIN_NAME'] = profile.get('user_domain_name', 'Default')
        env['OS_PROJECT_DOMAIN_ID'] = profile.get('project_domain_id', 'default')
        
        # Run openstack CLI với các args từ user
        cmd = ['openstack'] + sys.argv[2:]
        try:
            result = subprocess.run(cmd, env=env)
            sys.exit(result.returncode)
        except FileNotFoundError:
            msg("Error: 'openstack' CLI not found. Install: pip3 install python-openstackclient", "red")
            sys.exit(1)
    
    # Normal mode với argparse
    parser = argparse.ArgumentParser(description="OpenStack Config Manager")
    parser.add_argument('action', choices=['setup', 'list', 'switch', 'discover', 'export'])
    parser.add_argument('--profile', help="Profile name")
    parser.add_argument('--output', default='terraform.tfvars', help="Output file")
    args = parser.parse_args()
    
    mgr = OpenStackConfigManager()
    mgr.load_config()
    
    if args.action == 'setup':
        mgr.interactive_setup()
    elif args.action == 'list':
        mgr.list_profiles()
    elif args.action == 'switch':
        if not args.profile:
            print("Error: --profile required")
            sys.exit(1)
        mgr.switch_profile(args.profile)
    elif args.action == 'discover':
        result = mgr.discover_resources()
        if result:
            print(json.dumps(result, indent=2))
    elif args.action == 'export':
        mgr.export_terraform_vars(args.output)
