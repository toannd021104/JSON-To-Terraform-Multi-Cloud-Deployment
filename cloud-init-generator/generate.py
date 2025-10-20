#!/usr/bin/env python3
import argparse
import json
import sys
from typing import Any, Dict
import yaml
from validate_json import validate

class literal_str(str):
    """Custom string class để force YAML dùng | style"""
    pass

def literal_presenter(dumper, data):
    """Custom presenter cho literal string"""
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')

# Register custom presenter
yaml.add_representer(literal_str, literal_presenter)

class InlineList(list):
    pass

def inline_list_representer(dumper, data):
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)

yaml.add_representer(InlineList, inline_list_representer)

class InlineDict(dict):
    pass

def inline_dict_representer(dumper, data):
    return dumper.represent_mapping('tag:yaml.org,2002:map', data, flow_style=True)

yaml.add_representer(InlineDict, inline_dict_representer)

def convert_to_cloud_config(data: Dict[str, Any]) -> Dict[str, Any]:
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
                if u.get("shell"):
                    user_entry["shell"] = u["shell"]
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
                elif u.get("plain_passwd"):
                    user_entry["plain_text_passwd"] = u["plain_passwd"]
                    user_entry["lock_passwd"] = False
                if u.get("ssh_authorized_keys"):
                    user_entry["ssh_authorized_keys"] = u["ssh_authorized_keys"]
                if u.get("sudo"):
                    user_entry["sudo"] = u["sudo"]
                if u.get("no_create_home"):
                    user_entry["no_create_home"] = True
                if u.get("no_user_group"):
                    user_entry["no_user_group"] = True
                if u.get("create_groups"):
                    user_entry["create_groups"] = True
                
                users.append(user_entry)
        
        if users:
            cloud_config["users"] = users
    
    # Package section (apt issue)
    if "package" in data:
        packages = []
        package_upgrade = False
        apt_source_needed = []
        
        if "runcmd" not in cloud_config:
            cloud_config["runcmd"] = []
        
        for pkg in data["package"]:
            pkg_name = pkg["name"]
            ensure = pkg["ensure"]
            manager = pkg.get("manager", "apt")
            options = pkg.get("options", [])
            
            # Xử lý package install/upgrade thông thường
            if ensure in ["present", "latest"]:
                if ensure == "latest":
                    package_upgrade = True
                
                # Thêm vào packages list (cho cloud-init tự động cài)
                if pkg.get("version"):
                    packages.append(f"{pkg_name}={pkg['version']}")
                else:
                    packages.append(pkg_name)
                
                # Handle package source
                if pkg.get("source"):
                    apt_source_needed.append(pkg)
                
                # Nếu có options phức tạp, dùng runcmd thay vì packages
                if options or pkg.get("configfiles") or pkg.get("mark_hold") or pkg.get("adminfile"):
                    # Xóa khỏi packages list, sẽ cài qua runcmd
                    if pkg_name in packages:
                        packages.remove(pkg_name)
                    if pkg.get("version") and f"{pkg_name}={pkg['version']}" in packages:
                        packages.remove(f"{pkg_name}={pkg['version']}")
                    
                    # Build install command với options
                    cmd_parts = [manager]
                    
                    if manager == "apt":
                        cmd_parts.append("install")
                    elif manager == "yum":
                        cmd_parts.append("install")
                    
                    # Thêm options
                    if options:
                        cmd_parts.extend(options)
                    
                    # Thêm configfiles option
                    if pkg.get("configfiles") == "keep":
                        cmd_parts.append("-o Dpkg::Options::=--force-confold")
                    elif pkg.get("configfiles") == "replace":
                        cmd_parts.append("-o Dpkg::Options::=--force-confnew")
                    
                    # Thêm package name
                    if pkg.get("version"):
                        cmd_parts.append(f"{pkg_name}={pkg['version']}")
                    else:
                        cmd_parts.append(pkg_name)
                    
                    cloud_config["runcmd"].append(" ".join(cmd_parts))
                    
                    # Mark hold nếu cần
                    if pkg.get("mark_hold"):
                        cloud_config["runcmd"].append(f"apt-mark hold {pkg_name}")
            
            # Xử lý package removal
            elif ensure == "absent":
                cmd_parts = [manager]
                
                if manager == "apt":
                    cmd_parts.append("remove")
                elif manager == "yum":
                    cmd_parts.append("remove")
                
                # Thêm options
                if options:
                    cmd_parts.extend(options)
                
                cmd_parts.append(pkg_name)
                
                cloud_config["runcmd"].append(" ".join(cmd_parts))
        
        # Thêm packages đơn giản (không có options)
        if packages:
            cloud_config["packages"] = packages
        
        if package_upgrade:
            cloud_config["package_upgrade"] = True
        
        # Thêm apt sources nếu cần
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
    
    # Service section
    if "service" in data:
        # Cloud-init doesn't have direct service management, use runcmd
        if "runcmd" not in cloud_config:
            cloud_config["runcmd"] = []
        
        for svc in data["service"]:
            cmd_parts = []
            
            if svc.get("enabled"):
                cmd_parts.append(f"systemctl enable {svc['name']}")
            
            # Build systemctl command với flags
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
                # Build command từng phần
                cmd_parts_list = []
                
                # Thêm timeout nếu có
                timeout = svc.get("timeout")
                if timeout:
                    cmd_parts_list.append(f"timeout {timeout}")
                
                # Thêm systemctl command
                cmd_parts_list.append("systemctl")
                
                # Thêm action
                cmd_parts_list.append(action)
                
                # Thêm flags nếu có (cho systemctl)
                flags = svc.get("flags", "").strip()
                if flags:
                    cmd_parts_list.append(flags)
                
                # Thêm service name
                cmd_parts_list.append(svc['name'])
                
                cmd = " ".join(cmd_parts_list)
                cmd_parts.append(cmd)
            
            if cmd_parts:
                # cloud_config["runcmd"].extend(cmd_parts)
                cloud_config["runcmd"].append(InlineList(cmd_parts))
    
    # Exec section (Not okay)
    if "exec" in data:
        if "runcmd" not in cloud_config:
            cloud_config["runcmd"] = []
        
        for ex in data["exec"]:
            cmd = ex["command"]
            
            # Build script parts
            script_parts = []
            
            # Add umask
            if ex.get("umask"):
                script_parts.append(f"umask {ex['umask']}")
            
            # Add environment
            if ex.get("environment"):
                for env in ex["environment"]:
                    script_parts.append(f"export {env}")
            
            # Add cwd
            if ex.get("cwd"):
                script_parts.append(f"cd {ex['cwd']}")
            
            # Build condition string
            conditions = []
            
            if ex.get("creates"):
                conditions.append(f"[ ! -e {ex['creates']} ]")
            
            if ex.get("onlyif"):
                conditions.append(f"({ex['onlyif']})")
            
            if ex.get("unless"):
                conditions.append(f"! ({ex['unless']})")
            
            # Combine condition + command
            if conditions:
                full_cmd = " && ".join(conditions) + f" && {cmd}"
            else:
                full_cmd = cmd
            
            script_parts.append(full_cmd)
            
            # Join all parts
            full_script = " && ".join(script_parts)  # Dùng && thay vì ;
            
            # Wrap with timeout
            if ex.get("timeout"):
                # Dùng double quotes bên ngoài, escape internal quotes
                escaped_script = full_script.replace('\\', '\\\\').replace('"', '\\"')
                full_script = f'timeout {ex["timeout"]} sh -c "{escaped_script}"'

            if ex.get("user"):
                # Dùng single quotes bên ngoài, escape single quotes bên trong
                escaped_script = full_script.replace("'", "'\\''")
                full_script = f"su -s /bin/bash {ex['user']} -c '{escaped_script}'"
            
            # Add retry wrapper
            if ex.get("tries") and ex["tries"] > 1:
                tries = ex["tries"]
                sleep = ex.get("try_sleep", 5)
                full_script = f"for i in $(seq 1 {tries}); do {full_script} && break || sleep {sleep}; done"
            
            # Dùng InlineList để format [sh, -c, script]
            cloud_config["runcmd"].append(InlineList(["sh", "-c", full_script]))


    # SSH config section
    if "ssh_config" in data:
        ssh = data["ssh_config"]
        
        if ssh.get("ssh_deletekeys"):
            cloud_config["ssh_deletekeys"] = True
        if ssh.get("ssh_genkeytypes"):
            cloud_config["ssh_genkeytypes"] = InlineList(ssh["ssh_genkeytypes"])
        if ssh.get("disable_root"):
            cloud_config["disable_root"] = True
        if ssh.get("ssh_publish_hostkeys"):
            ssh_publish = ssh["ssh_publish_hostkeys"]
            
            # Nếu có blacklist, convert thành InlineList
            if isinstance(ssh_publish, dict) and "blacklist" in ssh_publish:
                ssh_publish = ssh_publish.copy()  # Tránh modify original
                ssh_publish["blacklist"] = InlineList(ssh_publish["blacklist"])
            
            cloud_config["ssh_publish_hostkeys"] = ssh_publish
    
    # Bootcmd section (Not list format)
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
                # debconf_selections là dict, mỗi value cần format multiline
                debconf = {}
                for pkg_name, selections in value.items():
                    cleaned = selections.replace('\\n', '\n').strip()
                    debconf[pkg_name] = literal_str(cleaned + '\n')
                apt_config["debconf_selections"] = debconf
            else:
                apt_config[key] = value
        
        if apt_config:
            cloud_config["apt"] = apt_config
        
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
        print("\n❌ Validation failed. Conversion aborted.", file=sys.stderr)
        sys.exit(1)
    
    print("✅ Validation passed. Starting conversion...\n")
    
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
        print(f"✅ Cloud-config written to: {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()