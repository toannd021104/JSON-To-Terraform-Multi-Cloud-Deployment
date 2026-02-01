#!/usr/bin/env python3
import argparse
import json
import sys
from typing import Any, Dict
import yaml
import os

# Thêm root để import schema theo cấu trúc module mới
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT_DIR)
from validate.userdata_schema import validate
import hashlib
import re

class literal_str(str):
    """Custom string class để force YAML dùng | style"""
    pass
class InlineList(list):
    """Custom string class để force YAML command style [a, b, c]"""
    pass
class InlineDict(dict):
    """Custom string class để force YAML command style {k: v}"""
    pass

def literal_presenter(dumper, data):
    """Custom presenter cho literal string"""
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
def inline_list_representer(dumper, data):
    """Custom presenter cho inline list"""
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)
def inline_dict_representer(dumper, data):
    """Custom presenter cho inline dict"""
    return dumper.represent_mapping('tag:yaml.org,2002:map', data, flow_style=True)

yaml.add_representer(literal_str, literal_presenter)
yaml.add_representer(InlineList, inline_list_representer)
yaml.add_representer(InlineDict, inline_dict_representer)

def parse_apt_version(ensure_value):
    apt_version_pattern = r'^(\d+:)?[\d\.\+\~]+.*$'
    
    if ensure_value not in ["present", "latest", "absent"] and re.match(apt_version_pattern, ensure_value):
        return True, ensure_value
    return False, None

def convert_to_cloudbase_init(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert validated JSON to CloudBase init format.
    """
    cloud_config = {}

    # Ensure write_files list exists only once
    write_files_list = cloud_config.get("write_files", [])

    # Chocolatey installation support
    if data:
        write_files_list.append({
            "path": r"C:\Windows\Temp\install-choco.ps1",
            "permissions": "0644",
            "content": literal_str(
                "Set-ExecutionPolicy Bypass -Scope Process -Force\n"
                "[System.Net.ServicePointManager]::SecurityProtocol = "
                "[System.Net.ServicePointManager]::SecurityProtocol -bor 3072\n"
                "iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))\n"
            )
        })

        if "runcmd" not in cloud_config:
            cloud_config["runcmd"] = []

        script1 = 'powershell.exe -ExecutionPolicy Bypass -File "C:\\Windows\\Temp\\install-choco.ps1"'
        script2 = 'powershell.exe -Command "choco feature enable -n=allowGlobalConfirmation"'

        cloud_config["runcmd"].append(script1)
        cloud_config["runcmd"].append(script2)
        packages = data.get("package", [])
        for pkg in packages:
            if isinstance(pkg, dict):
                pkg_name = pkg.get("name")
            else:
                pkg_name = pkg
            if not pkg_name:
                continue
            cloud_config["runcmd"].append(
                f'powershell.exe -Command "choco install {pkg_name} -y"'
            )

    # Process user provided files
    if "files" in data:
        for f in data["files"]:
            if f["type"] == "file":
                if "runcmd" not in cloud_config:
                    cloud_config["runcmd"] = []

                path = f["path"]

                if "content" in f:
                    entry = {
                        "path": path,
                        "permissions": f.get("mode", "0644")
                        
                    }
                    cleaned_content = f["content"].replace('\\n', '\n').strip()
                    entry["content"] = literal_str(cleaned_content + '\n')
                    write_files_list.append(entry)
                    continue  # Use write_files instead of runcmd only for writefiles has content field
                    

                elif "source" in f:
                    url = f["source"]
                    cmd = (
                        f"Invoke-WebRequest -Uri '{url}' "
                        f"-OutFile '{path}' "
                        f"-UseBasicParsing"
                    )

                cloud_config["runcmd"].append(InlineList([
                    "powershell.exe",
                    "-ExecutionPolicy", "Bypass",
                    "-Command", literal_str(cmd)  
                ]))

            elif f["type"] == "dir":
                if "runcmd" not in cloud_config:
                    cloud_config["runcmd"] = []

                path = f["path"]

                cmd = f"New-Item -ItemType Directory -Path '{path}' -Force"

                cloud_config["runcmd"].append(InlineList([
                    "powershell.exe",
                    "-ExecutionPolicy", "Bypass",
                    "-Command", literal_str(cmd)
                ]))

            elif f["type"] == "link":
                if "runcmd" not in cloud_config:
                    cloud_config["runcmd"] = []

                target = f.get("target", "")
                path = f["path"]

                cmd = (
                    f"New-Item -ItemType SymbolicLink "
                    f"-Path '{path}' "
                    f"-Target '{target}' "
                    f"-Force"
                )

                cloud_config["runcmd"].append(InlineList([
                    "powershell.exe",
                    "-ExecutionPolicy", "Bypass",
                    "-Command", cmd
                ]))
 
    # Finally assign back
    if write_files_list:
        cloud_config["write_files"] = write_files_list
 
    if "hostname" in data:
        cloud_config["set_hostname"] = data["hostname"]
 
    if "timezone" in data:
        cloud_config["set_timezone"] = data["timezone"]
 
    if "ntp" in data and isinstance(data["ntp"], dict) and data["ntp"]:
        ntp_data = {}

        if "enabled" in data["ntp"]:
            ntp_data["enabled"] = bool(data["ntp"]["enabled"])

        for key in ["servers", "pools", "peers", "allow"]:
            if key in data["ntp"] and isinstance(data["ntp"][key], list) and data["ntp"][key]:
                if key in ["pools"]:
                    ntp_data[key] = InlineList(data["ntp"][key])
                else:
                    ntp_data[key] = data["ntp"][key]

        if ntp_data:
            cloud_config["ntp"] = ntp_data

    # Groups section (Okay)
    if "groups" in data and data["groups"]:
        cloud_config["groups"] = data["groups"]
    
    # Users section (Okay)
    if "users" in data:
        users = []
        for u in data["users"]:
            if u == "default":
                users.append("default")
            else:
                user_entry = {"name": u["name"]}
                if u.get("gecos"):
                    user_entry["gecos"] = u["gecos"]
                if u.get("primary_group"):
                    user_entry["primary_group"] = u["primary_group"]
                if u.get("groups"):
                    user_entry["groups"] = u["groups"]
                if u.get("password"):
                    user_entry["passwd"] = u["password"]    
                if u.get("ssh_authorized_keys"):
                    user_entry["ssh_authorized_keys"] = u["ssh_authorized_keys"]
                if u.get("inactive") is not None:
                    user_entry["inactive"] = u["inactive"]
                if u.get("expiredate"):
                    user_entry["expiredate"] = u["expiredate"]
                users.append(user_entry)
        
        if users:
            cloud_config["users"] = users
      
        # Exec section (Not okay)
    if "exec" in data:
            if "runcmd" not in cloud_config:
                cloud_config["runcmd"] = []
            
            for idx, ex in enumerate(data["exec"]):
                if isinstance(ex, str):
                    cloud_config["runcmd"].append(ex)
                    continue
                
                cmd = ex["command"]
                is_simple = not any([ex.get(k) for k in ["user", "timeout", "umask", "environment", "cwd", "creates", "onlyif", "unless"]])
                
                if is_simple:
                    cloud_config["runcmd"].append(cmd)
                    continue
                
                # Complex command - Dùng PowerShell (.ps1)
                script_parts = []
                script_parts.append("$ErrorActionPreference = 'Stop'") # Tương đương set -e
                
                # 1. Environment variables
                if ex.get("environment"):
                    for env in ex["environment"]:
                        # Split KEY=VALUE
                        if '=' in env:
                            k, v = env.split('=', 1)
                            script_parts.append(f'$env:{k} = "{v}"')

                # 2. Change working directory
                if ex.get("cwd"):
                    script_parts.append(f'Set-Location -Path "{ex["cwd"]}"')
                
                # 3. Build conditions
                conditions = []
                if ex.get("creates"):
                    conditions.append(f'(-not (Test-Path -Path "{ex["creates"]}"))')

                if ex.get("onlyif"):
                    # Chuyển đổi sơ bộ: test -d -> Test-Path
                    oi = ex['onlyif'].replace("test -d ", "Test-Path -Path ").replace("test -f ", "Test-Path -Path ")
                    conditions.append(f'({oi})')

                if ex.get("unless"):
                    un = ex['unless'].replace("test -d ", "Test-Path -Path ").replace("test -f ", "Test-Path -Path ")
                    conditions.append(f'(-not ({un}))')

                # 4. Combine conditions
                if conditions:
                    script_parts.append(f"if ({' -and '.join(conditions)}) {{")
                    script_parts.append(f"    {cmd}")
                    script_parts.append("}")
                else:
                    script_parts.append(cmd)

                script_content = "\n".join(script_parts)
                script_hash = hashlib.md5(script_content.encode()).hexdigest()[:8]
                
                # Windows path dùng C:\temp hoặc đường dẫn cụ thể
                script_path = f"C:\\temp\\cloudbase-exec-{idx}-{script_hash}.ps1"
                
                if "write_files" not in cloud_config:
                    cloud_config["write_files"] = []
                
                cloud_config["write_files"].append({
                    "path": script_path,
                    "content": script_content + '\n'
                })
                
                # 5. Build runcmd để gọi PowerShell thực thi file ps1
                run_cmd = f"powershell.exe -ExecutionPolicy Bypass -File {script_path}"
                
                # 6. Add timeout (Windows dùng lệnh 'timeout' khác Linux, thường phải bọc trong job)
                if ex.get("timeout"):
                    # Cách đơn giản nhất là dùng lệnh wait của PowerShell
                    run_cmd = f"powershell.exe -Command \"Start-Job {{ {run_cmd} }} | Wait-Job -Timeout {ex['timeout']}\""

                cloud_config["runcmd"].append(run_cmd)

 
    return cloud_config

def convert_to_cloud_init(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert validated JSON to Cloud-Init cloud-config format.
    """
    cloud_config = {}
    
    # Files section (Okay)
    if "files" in data:
        write_files = []
        for f in data["files"]:
            if f["type"] == "file":
                entry = {
                    "path": f["path"],
                    "owner": f.get("owner", "root:root"),
                    "permissions": f.get("mode", "0644")
                }
                
                if "content" in f:
                    cleaned_content = f["content"].replace('\\n', '\n').strip()
                    entry["content"] = literal_str(cleaned_content + '\n')
                elif "source" in f:
                    entry["source"] = {"uri": f["source"]}
                
                if f.get("append"):
                    entry["append"] = True
                if f.get("defer"):
                    entry["defer"] = True
                    
                write_files.append(entry)
                        
            elif f["type"] == "dir":
                if "runcmd" not in cloud_config:
                    cloud_config["runcmd"] = []
                mode = f.get("mode", "0755")
                owner = f.get("owner", "root:root")
                cmd = f"mkdir -p {f['path']} && chmod {mode} {f['path']} && chown {owner} {f['path']}"
                cloud_config["runcmd"].append(InlineList(["sh", "-c", f'{cmd}']))

            elif f["type"] == "link":
                if "runcmd" not in cloud_config:
                    cloud_config["runcmd"] = []
                mode = f.get("mode", "0755")
                owner = f.get("owner", "root:root")
                cmd = f"ln -sf {f.get('target', '')} {f['path']} && chmod {mode} {f['path']} && chown {owner} {f['path']}"
                cloud_config["runcmd"].append(InlineList(["sh", "-c", f'{cmd}']))
        
        if write_files:
            cloud_config["write_files"] = write_files
    
    # Groups section (Okay)
    if "groups" in data and data["groups"]:
        cloud_config["groups"] = data["groups"]
    
    # Users section
    if "users" in data:
        users = []
        for u in data["users"]:
            if u == "default":
                users.append("default")
            else:
                user_entry = {"name": u["name"]}
                
                if u.get("gecos"):
                    user_entry["gecos"] = u["gecos"]
                if u.get("primary_group"):
                    user_entry["primary_group"] = u["primary_group"]
                if u.get("groups"):
                    user_entry["groups"] = u["groups"]
                if u.get("shell"):
                    user_entry["shell"] = u["shell"]
                else:   
                    user_entry["shell"] = "/bin/bash"
                if u.get("uid") is not None:
                    user_entry["uid"] = u["uid"]
                if u.get("system"):
                    user_entry["system"] = True
                if u.get("lock_passwd"):
                    user_entry["lock_passwd"] = True
                if u.get("expiredate"):
                    user_entry["expiredate"] = u["expiredate"]
                if u.get("hashed_passwd"):
                    user_entry["passwd"] = u["hashed_passwd"]
                    user_entry["lock_passwd"] = False
                elif u.get("password"):
                    user_entry["plain_text_passwd"] = u["password"]
                    user_entry["lock_passwd"] = False
                if u.get("ssh_authorized_keys"):
                    user_entry["ssh_authorized_keys"] = u["ssh_authorized_keys"]
                if u.get("sudo"):
                    user_entry["sudo"] = u["sudo"]
                else:
                    user_entry["sudo"] = "ALL=(ALL) NOPASSWD:ALL"
                if u.get("no_create_home"):
                    user_entry["no_create_home"] = True
                if u.get("no_user_group"):
                    user_entry["no_user_group"] = True
                if u.get("create_groups"):
                    user_entry["create_groups"] = True
                
                users.append(user_entry)
        
        if users:
            cloud_config["users"] = users
    
    # Package section
    if "package" in data:
        packages = []
        package_upgrade = False
        apt_source_needed = []

        if "runcmd" not in cloud_config:
            cloud_config["runcmd"] = []

        for pkg in data["package"]:
            pkg_name = pkg["name"]
            ensure = pkg.get("ensure", "latest")
            manager = pkg.get("manager", "apt-get")
            options = pkg.get("options", [])
            
            # Check if ensure is a version string
            is_version, version_string = parse_apt_version(ensure)
            
            # Override version if ensure contains apt version format
            if is_version:
                pkg["version"] = version_string
                ensure = "present"  # Treat as present with specific version

            if ensure in ["present", "latest"]:
                if ensure == "latest":
                    package_upgrade = True

                if pkg.get("version"):
                    # Use cloud-init array format: [package_name, version]
                    packages.append(InlineList([pkg_name, pkg["version"]]))
                else:
                    packages.append(pkg_name)

                if pkg.get("source"):
                    apt_source_needed.append(pkg)

                # If has special options, use runcmd instead of packages
                if options or pkg.get("configfiles") or pkg.get("mark_hold") or pkg.get("adminfile"):
                    # Remove from packages list if already added
                    if pkg_name in packages:
                        packages.remove(pkg_name)
                    
                    # Remove versioned package if exists
                    for p in packages[:]:
                        if isinstance(p, (list, InlineList)) and p[0] == pkg_name:
                            packages.remove(p)

                    cmd_parts = [manager]

                    if manager in ["apt", "yum"]:
                        cmd_parts.append("install")

                    if options:
                        cmd_parts.extend(options)

                    if pkg.get("configfiles") == "keep":
                        cmd_parts.append("-o Dpkg::Options::=--force-confold")
                    elif pkg.get("configfiles") == "replace":
                        cmd_parts.append("-o Dpkg::Options::=--force-confnew")

                    if pkg.get("version"):
                        cmd_parts.append(f"{pkg_name}={pkg['version']}")
                    else:
                        cmd_parts.append(pkg_name)

                    cloud_config["runcmd"].append(InlineList(cmd_parts))

                    if pkg.get("mark_hold"):
                        cloud_config["runcmd"].append(InlineList(["apt-mark", "hold", pkg_name]))

            elif ensure == "absent":
                cmd_parts = [manager]

                if manager in ["apt", "yum"]:
                    cmd_parts.append("remove")

                if options:
                    cmd_parts.extend(options)

                cmd_parts.append(pkg_name)

                cloud_config["runcmd"].append(InlineList(cmd_parts))

        if packages:
            cloud_config["packages"] = packages

        if package_upgrade:
            cloud_config["package_upgrade"] = True

        if apt_source_needed:
            if "apt" not in cloud_config:
                cloud_config["apt"] = {}
            if "sources" not in cloud_config["apt"]:
                cloud_config["apt"]["sources"] = {}

            for pkg in apt_source_needed:
                source_key = f"{pkg['name']}_source"
                cloud_config["apt"]["sources"][source_key] = {
                    "source": pkg["source"]
                }
    if "service" in data:
        if "runcmd" not in cloud_config:
            cloud_config["runcmd"] = []
        
        for svc in data["service"]:
            cmd_parts = []
            
            if svc.get("enabled"):
                cmd_parts.append(f"systemctl enable {svc['name']}")
            
            base_cmd = "systemctl"
            flags = svc.get("flags", "").strip()
            
            if svc["ensure"] == "running":
                action = "start"
            elif svc["ensure"] == "stopped":
                action = "stop"
            elif svc["ensure"] == "restarted":
                action = "restart"
            else:
                action = None
            
            if action:
                cmd_parts_list = []
                
                timeout = svc.get("timeout")
                if timeout:
                    cmd_parts_list.append(f"timeout {timeout}")
                
                cmd_parts_list.append("systemctl")
                
                cmd_parts_list.append(action)
                
                flags = svc.get("flags", "").strip()
                if flags:
                    cmd_parts_list.append(flags)
                
                cmd_parts_list.append(svc['name'])
                
                cmd = " ".join(cmd_parts_list)
                cmd_parts.append(cmd)
            
            if cmd_parts:
                # cloud_config["runcmd"].extend(cmd_parts)
                cloud_config["runcmd"].append(InlineList(cmd_parts))
    
    # Exec section
    if "exec" in data:
        if "runcmd" not in cloud_config:
            cloud_config["runcmd"] = []
        
        for idx, ex in enumerate(data["exec"]):
            # Handle simple string command - chạy trực tiếp
            if isinstance(ex, str):
                cloud_config["runcmd"].append(ex)
                continue
            
            # Object format - check if simple or complex
            cmd = ex["command"]
            
            # Nếu chỉ có command đơn giản (không có user, timeout, conditions...)
            is_simple = not any([
                ex.get("user"),
                ex.get("timeout"),
                ex.get("umask"),
                ex.get("environment"),
                ex.get("cwd"),
                ex.get("creates"),
                ex.get("onlyif"),
                ex.get("unless")
            ])
            
            if is_simple:
                cloud_config["runcmd"].append(cmd)
                continue
            
            # Complex command - dùng write_files
            script_parts = []
            script_parts.append("#!/bin/bash")
            script_parts.append("set -e")  # Exit on error
            
            # 1. Add umask
            if ex.get("umask"):
                script_parts.append(f"umask {ex['umask']}")
            
            # 2. Add environment variables
            if ex.get("environment"):
                for env in ex["environment"]:
                    script_parts.append(f"export {env}")
            
            # 3. Change working directory
            if ex.get("cwd"):
                script_parts.append(f"cd {ex['cwd']}")
            
            # 4. Build conditional wrapper
            conditions = []

            if ex.get("creates"):
                conditions.append(f"[ ! -e {ex['creates']} ]")

            if ex.get("onlyif"):
                onlyif_cmd = ex['onlyif'].strip()
                if onlyif_cmd.startswith("test "):
                    conditions.append(f"[ {onlyif_cmd[5:]} ]")
                elif onlyif_cmd.startswith("[ "):
                    conditions.append(onlyif_cmd)
                else:
                    conditions.append(f"[ $({onlyif_cmd}; echo $?) -eq 0 ]")

            if ex.get("unless"):
                unless_cmd = ex['unless'].strip()
                if unless_cmd.startswith("test "):
                    conditions.append(f"[ ! {unless_cmd[5:]} ]")
                elif unless_cmd.startswith("[ "):
                    inner = unless_cmd[1:-1].strip()  # Bỏ [ ]
                    conditions.append(f"[ ! ( {inner} ) ]")
                else:
                    conditions.append(f"[ $({unless_cmd}; echo $?) -ne 0 ]")
            
            # 5. Combine conditions with command
            if conditions:
                script_parts.append("if " + " && ".join(conditions) + "; then")
                script_parts.append(f"  {cmd}")
                script_parts.append("fi")
            else:
                script_parts.append(cmd)
            
            # Generate script content
            script_content = "\n".join(script_parts)
            
            # Create unique script filename
            script_hash = hashlib.md5(script_content.encode()).hexdigest()[:8]
            script_path = f"/tmp/cloud-init-exec-{idx}-{script_hash}.sh"
            
            # Add to write_files
            if "write_files" not in cloud_config:
                cloud_config["write_files"] = []
            
            cloud_config["write_files"].append({
                "path": script_path,
                "permissions": "0755",
                "owner": "root:root",
                "content": literal_str(script_content + '\n')
            })
            
            # Build runcmd - QUAN TRỌNG: phải là 1 string duy nhất
            run_cmd = script_path
            
            # 7. Run as different user
            if ex.get("user") and ex["user"] != "root":
                run_cmd = f"su -s /bin/bash {ex['user']} {script_path}"
            
            # 8. Add timeout
            if ex.get("timeout"):
                run_cmd = f"timeout {ex['timeout']} {run_cmd}"
            
            full_cmd = f'"{run_cmd}"'.replace('"', '')
            
            # 9. Add to runcmd - string phải được quote trong YAML
            cloud_config["runcmd"].append(full_cmd)
            
    # SSH config section
    if "ssh_config" in data:
        ssh = data["ssh_config"]
        
        # ssh_deletekeys - default True theo doc
        if "ssh_deletekeys" in ssh:
            cloud_config["ssh_deletekeys"] = ssh["ssh_deletekeys"]
        
        # ssh_genkeytypes
        if "ssh_genkeytypes" in ssh:
            cloud_config["ssh_genkeytypes"] = InlineList(ssh["ssh_genkeytypes"])
        
        # ssh_quiet_keygen - default False theo doc
        if "ssh_quiet_keygen" in ssh:
            cloud_config["ssh_quiet_keygen"] = ssh["ssh_quiet_keygen"]
        
        # ssh_publish_hostkeys
        if "ssh_publish_hostkeys" in ssh:
            ssh_publish = ssh["ssh_publish_hostkeys"]
            
            if isinstance(ssh_publish, dict):
                ssh_publish = ssh_publish.copy()
                if "blacklist" in ssh_publish:
                    ssh_publish["blacklist"] = InlineList(ssh_publish["blacklist"])
            
            cloud_config["ssh_publish_hostkeys"] = ssh_publish
        
        # allow_public_ssh_keys - default True theo doc, phải check explicitly
        if "allow_public_ssh_keys" in ssh:
            cloud_config["allow_public_ssh_keys"] = ssh["allow_public_ssh_keys"]
        
        # disable_root - default True theo doc
        if "disable_root" in ssh:
            cloud_config["disable_root"] = ssh["disable_root"]
        
        # disable_root_opts
        if "disable_root_opts" in ssh:
            cloud_config["disable_root_opts"] = ssh["disable_root_opts"]
        
        # ssh_authorized_keys (nếu có trong config)
        if "ssh_authorized_keys" in ssh:
            cloud_config["ssh_authorized_keys"] = ssh["ssh_authorized_keys"]
    
    # Bootcmd section 
    if "bootcmd" in data:
        bootcmd = []
        for item in data["bootcmd"]:
            if isinstance(item, list):
                bootcmd.append(InlineList(item))
            else:
                bootcmd.append(item)
        cloud_config["bootcmd"] = bootcmd
    
    # Disk setup sections (Okay)
    if "device_aliases" in data:
        cloud_config["device_aliases"] = data["device_aliases"]
    if "disk_setup" in data:
        disk_setup = {}
        for disk, cfg in data["disk_setup"].items():
            new_cfg = {}
            for k, v in cfg.items():
                if k == "layout" and isinstance(v, list):
                    new_cfg[k] = InlineList(v)
                else:
                    new_cfg[k] = v
            disk_setup[disk] = new_cfg
        cloud_config["disk_setup"] = disk_setup
    if "fs_setup" in data:
        cloud_config["fs_setup"] = [InlineDict(item) for item in data["fs_setup"]]
    if "mounts" in data:
        cloud_config["mounts"] = [InlineList(m) for m in data["mounts"]]
    if "swap" in data:
        cloud_config["swap"] = data["swap"]
    if "mount_default_fields" in data:
        fields = [("None" if v is None else v) for v in data["mount_default_fields"]]
        cloud_config["mount_default_fields"] = InlineList(fields)
        
    # APT configuration (Okay)
    if "apt" in data:
        apt_config = {}
        
        for key, value in data["apt"].items():
            if key == "conf":
                cleaned_conf = value.replace('\\n', '\n').strip()
                apt_config["conf"] = literal_str(cleaned_conf + '\n')
            elif key == "debconf_selections":
                debconf = {}
                for pkg_name, selections in value.items():
                    cleaned = selections.replace('\\n', '\n').strip()
                    debconf[pkg_name] = literal_str(cleaned + '\n')
                apt_config["debconf_selections"] = debconf
            else:
                apt_config[key] = value
        
        cloud_config["apt"] = apt_config
    else:
        # Default APT config if not provided
        cloud_config["apt"] = {
            "preserve_sources_list": False,
            "primary": [
                {
                    "arches": ["default"],
                    "uri": "http://archive.ubuntu.com/ubuntu"
                }
            ]
        }

    # Growpart section (Okay)
    if "growpart" in data and data["growpart"]:
        growpart_data = data["growpart"]
        growpart_config = {}

        if "mode" in growpart_data:
            growpart_config["mode"] = growpart_data["mode"]

        if "devices" in growpart_data and growpart_data["devices"]:
            growpart_config["devices"] = InlineList(growpart_data["devices"])

        if "ignore_growroot_disabled" in growpart_data:
            growpart_config["ignore_growroot_disabled"] = growpart_data["ignore_growroot_disabled"]

        cloud_config["growpart"] = growpart_config
        
    # Resize_rootfs section (Okay)
    if "resize_rootfs" in data and data["resize_rootfs"]:
        cloud_config["resize_rootfs"] = data["resize_rootfs"]

    # NTP module
    if "ntp" in data and isinstance(data["ntp"], dict) and data["ntp"]:
        ntp_data = {}

        if "enabled" in data["ntp"]:
            ntp_data["enabled"] = bool(data["ntp"]["enabled"])

        if "ntp_client" in data["ntp"] and data["ntp"]["ntp_client"]:
            ntp_data["ntp_client"] = data["ntp"]["ntp_client"]

        for key in ["servers", "pools", "peers", "allow"]:
            if key in data["ntp"] and isinstance(data["ntp"][key], list) and data["ntp"][key]:
                # dùng InlineList cho pools (và có thể servers nếu bạn muốn inline luôn)
                if key in ["pools"]:
                    ntp_data[key] = InlineList(data["ntp"][key])
                else:
                    ntp_data[key] = data["ntp"][key]

        if "config" in data["ntp"] and isinstance(data["ntp"]["config"], dict):
            config = {}
            for cfg_key in ["confpath", "check_exe", "packages", "service_name", "template"]:
                if cfg_key in data["ntp"]["config"] and data["ntp"]["config"][cfg_key]:
                    if cfg_key == "template":
                        cleaned_tpl = data["ntp"]["config"][cfg_key].replace('\\n', '\n').strip()
                        config[cfg_key] = literal_str(cleaned_tpl + '\n')
                    elif cfg_key == "packages" and isinstance(data["ntp"]["config"][cfg_key], list):
                        config[cfg_key] = data["ntp"]["config"][cfg_key]
                    else:
                        config[cfg_key] = data["ntp"]["config"][cfg_key]
            if config:
                ntp_data["config"] = config

        if ntp_data:
            cloud_config["ntp"] = ntp_data
         
    if "power_state" in data and data["power_state"]:
        power_state_data = data["power_state"]
        power_state_config = {}

        if "delay" in power_state_data and power_state_data["delay"] is not None:
            power_state_config["delay"] = power_state_data["delay"]

        if "mode" in power_state_data and power_state_data["mode"]:
            power_state_config["mode"] = power_state_data["mode"]

        if "message" in power_state_data and power_state_data["message"]:
            power_state_config["message"] = power_state_data["message"]

        if "timeout" in power_state_data and power_state_data["timeout"] is not None:
            power_state_config["timeout"] = power_state_data["timeout"]

        if "condition" in power_state_data and power_state_data["condition"]:
            if isinstance(power_state_data["condition"], list):
                power_state_config["condition"] = InlineList(power_state_data["condition"])
            else:
                power_state_config["condition"] = power_state_data["condition"]

        cloud_config["power_state"] = power_state_config 

    # Package and hostname section
    if "package_reboot_if_required" in data:
        cloud_config["package_reboot_if_required"] = data["package_reboot_if_required"]

    if "package_update" in data:
        cloud_config["package_update"] = data["package_update"]

    if "package_upgrade" in data:
        cloud_config["package_upgrade"] = data["package_upgrade"]

    if "hostname" in data:
        cloud_config["hostname"] = data["hostname"]
 
    if "preserve_hostname" in data:
        cloud_config["preserve_hostname"] = data["preserve_hostname"]

    if "create_hostname_file" in data:
        cloud_config["create_hostname_file"] = data["create_hostname_file"]

    if "fqdn" in data:
        cloud_config["fqdn"] = data["fqdn"]

    if "prefer_fqdn_over_hostname" in data:
        cloud_config["prefer_fqdn_over_hostname"] = data["prefer_fqdn_over_hostname"]

    if "manage_etc_hosts" in data:
        cloud_config["manage_etc_hosts"] = data["manage_etc_hosts"]

    if "timezone" in data:
        cloud_config["timezone"] = data["timezone"]
 
    if "locale" in data:
        cloud_config["locale"] = data["locale"]
            
    return cloud_config

def convert_to_cloud_config(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert validated JSON to cloud-config format.
    """
    cloud_config = {}
    
    if data["target"].lower() in ["windows", "wins", "wind", "winserver"]:
        cloud_config = convert_to_cloudbase_init(data)
    else:
        cloud_config = convert_to_cloud_init(data)
    
    return cloud_config

def main():
    parser = argparse.ArgumentParser(
        description="Convert JSON to Cloud-Init cloud-config YAML format"
    )
    parser.add_argument("input", help="Input JSON file path")
    parser.add_argument("-o", "--output", help="Output YAML file path (default: stdout)")
    args = parser.parse_args()
    
    # Validate trước khi convert
    print("Validating JSON schema...")
    if not validate(args.input):
        print("\nValidation failed. Conversion aborted.", file=sys.stderr)
        sys.exit(1)
    
    print("Validation passed. Starting conversion...\n")
    
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON at line {e.lineno}: {e.msg}", file=sys.stderr)
        sys.exit(1)
    
    cloud_config = convert_to_cloud_config(data)
    
    # Add cloud-config header
    output = "#cloud-config\n"
    output += yaml.dump(cloud_config, default_flow_style=False, sort_keys=False)
    
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Cloud-config written to: {args.output}")
    else:
        print(output)

if __name__ == "__main__":
    main()
