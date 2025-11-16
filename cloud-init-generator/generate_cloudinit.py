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
        script3 = 'powershell.exe -Command "choco install git -y"'

        cloud_config["runcmd"].append(script1)
        cloud_config["runcmd"].append(script2)
        cloud_config["runcmd"].append(script3)

    # Process user provided files
    if "files" in data:
        for f in data["files"]:
            if f["type"] == "file":
                entry = {
                    "path": f["path"],
                    "permissions": f.get("mode", "0644")
                }

                if "content" in f:
                    cleaned = f["content"].replace('\\n', '\n').strip()
                    entry["content"] = literal_str(cleaned + '\n')
                elif "source" in f:
                    entry["source"] = {"uri": f["source"]}

                if "encoding" in f:
                    entry["encoding"] = f["encoding"]

                if f.get("append"):
                    entry["append"] = True
                if f.get("defer"):
                    entry["defer"] = True

                write_files_list.append(entry)

            elif f["type"] == "dir":
                if "runcmd" not in cloud_config:
                    cloud_config["runcmd"] = []

                mode = f.get("mode", "0755")
                owner = f.get("owner", "root:root")
                cmd = f"mkdir -p {f['path']} && chmod {mode} {f['path']} && chown {owner} {f['path']}"
                cloud_config["runcmd"].append(["sh", "-c", cmd])

            elif f["type"] == "link":
                if "runcmd" not in cloud_config:
                    cloud_config["runcmd"] = []

                mode = f.get("mode", "0755")
                owner = f.get("owner", "root:root")
                cmd = f"ln -sf {f.get('target', '')} {f['path']} && chmod {mode} {f['path']} && chown {owner} {f['path']}"
                cloud_config["runcmd"].append(["sh", "-c", cmd])

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
                if u.get("passwd"):
                    user_entry["passwd"] = u["passwd"]    
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
        
        for ex in data["exec"]:
            # Handle both string and object format
            if isinstance(ex, str):
                # Simple string command
                cloud_config["runcmd"].append(ex)
                continue
            
            # Object format with advanced options
            cmd = ex["command"]
            script_parts = []
            
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
            
            # 4. Build conditional checks
            conditions = []
            
            if ex.get("creates"):
                conditions.append(f"[ ! -e {ex['creates']} ]")
            
            if ex.get("onlyif"):
                conditions.append(f"({ex['onlyif']})")
            
            if ex.get("unless"):
                conditions.append(f"! ({ex['unless']})")
            
            # 5. Combine conditions with command
            if conditions:
                script_parts.append(" && ".join(conditions) + f" && {cmd}")
            else:
                script_parts.append(cmd)
            
            # 6. Join all parts with &&
            full_script = " && ".join(script_parts)
            
            # 7. Run as different user (nếu có và không phải root)
            if ex.get("user") and ex["user"] != "root":
                escaped_script = full_script.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'")
                full_script = f'su -s /bin/bash {ex["user"]} -c "{escaped_script}"'
            
            # 8. Add timeout wrapper (nếu có)
            if ex.get("timeout"):
                escaped_script = full_script.replace('\\', '\\\\').replace('"', '\\"')
                full_script = f'timeout {ex["timeout"]} sh -c "{escaped_script}"'
            
            # 9. Add retry logic (nếu có)
            if ex.get("tries") and ex["tries"] > 1:
                tries = ex["tries"]
                sleep = ex.get("try_sleep", 5)
                escaped_script = full_script.replace('\\', '\\\\').replace('"', '\\"')
                full_script = f'for i in $(seq 1 {tries}); do sh -c "{escaped_script}" && break || sleep {sleep}; done'
            
            # 10. Add to runcmd as [sh, -c, script]
            cloud_config["runcmd"].append(InlineList([full_script]))

 
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

            if ensure in ["present", "latest"]:
                if ensure == "latest":
                    package_upgrade = True

                if pkg.get("version"):
                    packages.append(f"{pkg_name}={pkg['version']}")
                else:
                    packages.append(pkg_name)

                if pkg.get("source"):
                    apt_source_needed.append(pkg)

                if options or pkg.get("configfiles") or pkg.get("mark_hold") or pkg.get("adminfile"):
                    if pkg_name in packages:
                        packages.remove(pkg_name)
                    if pkg.get("version") and f"{pkg_name}={pkg['version']}" in packages:
                        packages.remove(f"{pkg_name}={pkg['version']}")

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
    
    # Exec section (Not okay)
    if "exec" in data:
        if "runcmd" not in cloud_config:
            cloud_config["runcmd"] = []
        
        for ex in data["exec"]:
            # Handle both string and object format
            if isinstance(ex, str):
                # Simple string command
                cloud_config["runcmd"].append(InlineList(["sh", "-c", ex]))
                continue
            
            # Object format with advanced options
            cmd = ex["command"]
            script_parts = []
            
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
            
            # 4. Build conditional checks
            conditions = []
            
            if ex.get("creates"):
                conditions.append(f"[ ! -e {ex['creates']} ]")
            
            if ex.get("onlyif"):
                conditions.append(f"({ex['onlyif']})")
            
            if ex.get("unless"):
                conditions.append(f"! ({ex['unless']})")
            
            # 5. Combine conditions with command
            if conditions:
                script_parts.append(" && ".join(conditions) + f" && {cmd}")
            else:
                script_parts.append(cmd)
            
            # 6. Join all parts with &&
            full_script = " && ".join(script_parts)
            
            # 7. Run as different user (nếu có và không phải root)
            if ex.get("user") and ex["user"] != "root":
                escaped_script = full_script.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'")
                full_script = f'su -s /bin/bash {ex["user"]} -c "{escaped_script}"'
            
            # 8. Add timeout wrapper (nếu có)
            if ex.get("timeout"):
                escaped_script = full_script.replace('\\', '\\\\').replace('"', '\\"')
                full_script = f'timeout {ex["timeout"]} sh -c "{escaped_script}"'
            
            # 9. Add retry logic (nếu có)
            if ex.get("tries") and ex["tries"] > 1:
                tries = ex["tries"]
                sleep = ex.get("try_sleep", 5)
                escaped_script = full_script.replace('\\', '\\\\').replace('"', '\\"')
                full_script = f'for i in $(seq 1 {tries}); do sh -c "{escaped_script}" && break || sleep {sleep}; done'
            
            # 10. Add to runcmd as [sh, -c, script]
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
            
            if isinstance(ssh_publish, dict) and "blacklist" in ssh_publish:
                ssh_publish = ssh_publish.copy()
                ssh_publish["blacklist"] = InlineList(ssh_publish["blacklist"])
            
            cloud_config["ssh_publish_hostkeys"] = ssh_publish
    
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
        
        if apt_config:
            cloud_config["apt"] = apt_config

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