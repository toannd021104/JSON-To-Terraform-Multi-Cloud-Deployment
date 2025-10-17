#!/usr/bin/env python3
import argparse
import json
import sys
from typing import List
from jsonschema import Draft202012Validator, exceptions as js_exceptions

# Schema bạn đưa (dùng dạng dict Python, vì bạn viết True/False)
USER_DATA_SCHEMA = {
    "type": "object",
    "required": ["files", "groups", "users"],
    "additionalProperties": False,
    "properties": {
        "files": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["path", "type"],
                "properties": {
                    "path": {
                        "type": "string",
                        "pattern": r"^/(?:[^\n\0]+)$"
                    },
                    "type": {
                        "type": "string",
                        "enum": ["file", "dir", "link"],
                        "default": "file"
                    },
                    "content": {
                        "type": "string",
                        "default": ""
                    },
                    "backup": {
                        "type": "boolean",
                        "default": False
                    },
                    "owner": {
                        "type": "string",
                        "default": "root:root",
                        "pattern": r"^[a-z_][a-z0-9_-]*:[a-z_][a-z0-9_-]*$"
                    },
                    "mode": {
                        "type": "string",
                        "default": "0644",
                        "pattern": r"^[0-7]{3,4}$"
                    },
                    "source": {
                        "oneOf": [
                            {"type": "string", "minLength": 1},
                            {"type": "null"}
                        ]
                    },
                    "target": {
                        "type": ["string", "null"],
                        "default": "",
                        "pattern": r"^/.*"
                    },
                    "validate_cmd": {
                        "type": ["string", "null"],
                        "default": ""
                    },
                    "defer": {
                        "type": "boolean",
                        "default": False
                    },
                    "append": {
                        "type": "boolean",
                        "default": False
                    }
                },
                "allOf": [
                    {
                        "if": { "properties": { "type": { "const": "file" } }, "required": ["type"] },
                        "then": {
                            "not": { "required": ["target"] },
                            "allOf": [
                            {
                                "anyOf": [
                                { "required": ["content"] },
                                { "required": ["source"] }
                                ]
                            }
                            ]
                        }
                    },
                    {
                        "if": {
                            "properties": {"type": {"const": "dir"}},
                            "required": ["type"]
                        },
                        "then": {
                            "not": {
                                "anyOf": [
                                    {"required": ["content"]},
                                    {"required": ["source"]},
                                    {"required": ["append"]},
                                    {"required": ["validate_cmd"]},
                                    {"required": ["target"]}
                                ]
                            },
                            "properties": {
                                "mode": {"pattern": r"^[0-7]{3,4}$"}
                            }
                        }
                    },
                    {
                        "if": {
                            "properties": {"type": {"const": "link"}},
                            "required": ["type"]
                        },
                        "then": {
                            "required": ["target"],
                            "not": {
                                "anyOf": [
                                    {"required": ["content"]},
                                    {"required": ["source"]},
                                    {"required": ["append"]},
                                    {"required": ["validate_cmd"]}
                                ]
                            },
                            "properties": {
                                "mode": {"pattern": r"^[0-7]{3,4}$"}
                            }
                        }
                    }
                ]
            }
        },
        "groups": {
            "type": "array",
            "minItems": 0,
            "uniqueItems": True,
            "items": {
                "type": "string",
                "default": "",
                "minLength": 1,
                "pattern": "^[a-z_][a-z0-9_-]*$"
            }
        },
        "users": {
            "type": "array",
            "minItems": 0,
            "items": {
                "oneOf": [
                { "const": "default" },
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["name"],
                    "properties": {
                    "name": {
                        "type": ["string"],
                        "default": "",
                        "minLength": 1,
                        "pattern": "^[a-z_][a-z0-9_-]*$"
                    },
                    "gecos": { "type": ["string","null"], "default": "" },
                    "primary_group": {
                        "type": ["string","null"],
                        "default": "",
                        "pattern": "^[a-z_][a-z0-9_-]*$"
                    },
                    "groups": {
                        "type": "array",
                        "default": [],
                        "uniqueItems": True,
                        "items": {
                        "type": "string",
                        "minLength": 1,
                        "pattern": "^[a-z_][a-z0-9_-]*$"
                        }
                    },
                    "shell": {
                        "type": ["string","null"],
                        "default": "",
                        "pattern": "^[a-z_][a-z0-9_-]*$"
                    },
                    "uid": {
                        "type": ["integer","null"],
                        "default": "",
                        "minimum": 0,
                        "maximum": 60000
                    },
                    "system": { "type": "boolean", "default": False },
                    "lock_passwd": { "type": "boolean", "default": False },
                    "expiredate": {
                        "type": ["string","null"],
                        "default": "",
                        "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
                    },
                    "create_groups": { "type": "boolean", "default": False },
                    "hashed_passwd": { "type": ["string","null"], "default": "" },
                    "plain_passwd": { "type": ["string","null"], "default": "" },
                    "ssh_authorized_keys": {
                        "type": "array",
                        "default": [],
                        "items": {
                        "type": "string",
                        "minLength": 20,
                        "pattern": "^(ssh-(rsa|ed25519)|ecdsa-sha2-nistp(256|384|521)) [A-Za-z0-9+/=]+(?: .*)?$"
                        }
                    },
                    "sudo": { "type": ["string","null"], "default": "" },
                    "password_policy": {
                        "type": "object",
                        "default": {},
                        "additionalProperties": False,
                        "properties": {
                        "max_days": { "type": ["integer","null"], "default": 90, "minimum": 0 },
                        "min_days": { "type": ["integer","null"], "default": 7, "minimum": 0 },
                        "warn_days": { "type": ["integer","null"], "default": 7, "minimum": 0 }
                        }
                    },
                    "no_create_home": { "type": "boolean", "default": False },
                    "no_user_group": { "type": "boolean", "default": False }
                    },
                    "allOf": [
                    {
                        "if": { "properties": { "system": { "const": True } }, "required": ["system"] },
                        "then": { "properties": { "uid": { "type": ["integer","null"], "maximum": 999 } } }
                    },
                    {
                        "if": { "properties": { "system": { "const": False } }, "required": ["system"] },
                        "then": { "properties": { "uid": { "type": ["integer","null"], "minimum": 1000 } } }
                    },
                    {
                        "not": { "required": ["hashed_passwd", "plain_passwd"] }
                    },
                    {
                        "if": { "properties": { "lock_passwd": { "const": True } }, "required": ["lock_passwd"] },
                        "then": {
                        "not": {
                            "anyOf": [
                            { "required": ["hashed_passwd"] },
                            { "required": ["plain_passwd"] }
                            ]
                        }
                        }
                    }
                    ]
                }
            ]
        }
        },
        "service": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "ensure", "flags", "timeout"],
                "properties": {
                "name": {
                    "type": "string",
                    "minLength": 1,
                    "pattern": "^[^\\n\\r]+$"
                },
                "ensure": {
                    "type": "string",
                    "enum": ["running", "stopped", "restarted"],
                    "default": "running"
                },
                "enabled": {
                    "type": "boolean",
                    "default": True
                },
                "provider": {
                    "type": ["string", "null"],
                    "enum": ["systemd", "sysvinit", "windows", "launchd", "smf", ""],
                    "default": ""
                },
                "flags": {
                    "type": "string",
                    "default": ""
                },
                "timeout": {
                    "type": "integer",
                    "default": 30,
                    "minimum": 0,
                    "maximum": 3600
                },
                "depends_on": {
                    "type": "array",
                    "default": [],
                    "items": {
                    "type": "string",
                    "minLength": 1,
                    "pattern": "^[^\\n\\r]+$"
                    },
                    "uniqueItems": True
                }
                },
                "allOf": [
                {
                    "if": {
                    "properties": { "provider": { "const": "systemd" } },
                    "required": ["provider"]
                    },
                    "then": {
                    "properties": {
                        "name": {
                        "type": "string",
                        "pattern": "^[^\\s\\n\\r]+(\\.service)?$"
                        },
                        "flags": {
                        "type": "string",
                        "pattern": "^(|(--[A-Za-z0-9-]+)(\\s+--[A-Za-z0-9-]+)*)$"
                        }
                    }
                    }
                },
                {
                    "if": {
                    "properties": { "provider": { "const": "windows" } },
                    "required": ["provider"]
                    },
                    "then": {
                    "properties": {
                        "name": {
                        "type": "string",
                        "pattern": "^[^\\n\\r]+$"
                        }
                    }
                    }
                }
                ]
            }
        },
        "package": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": False,
        "required": ["name", "ensure"],
        "properties": {
          "name": {
            "type": "string",
            "minLength": 1,
            "pattern": "^[A-Za-z0-9._+:-]+$",
            "default": ""
          },
          "ensure": {
            "type": "string",
            "enum": ["present", "latest", "absent"],
            "default": "present"
          },
          "version": {
            "type": ["string", "null"],
            "default": ""
          },
          "manager": {
            "type": ["string", "null"],
            "enum": ["apt", "dnf", "yum", "zypper", "pacman", "apk", "brew", "choco", "winget", "msi", ""],
            "default": ""
          },
          "architecture": {
            "type": ["string", "null"],
            "default": ""
          },
          "reinstall": {
            "type": "boolean",
            "default": False
          },
          "allow_downgrade": {
            "type": "boolean",
            "default": False
          },
          "source": {
            "type": ["string", "null"],
            "default": "",
            "pattern": "^(https?://[^\\s]+|/[^\\s]*|[A-Za-z]:\\\\[^\\s]*)$"
          },
          "options": {
            "type": "array",
            "default": [],
            "items": { "type": "string" }
          },
          "configfiles": {
            "type": "string",
            "enum": ["keep", "replace", "overwrite"],
            "default": "keep"
          },
          "mark_hold": {
            "type": "boolean",
            "default": False
          },
          "adminfile": {
            "type": ["string", "null"],
            "default": "",
            "pattern": "^(|/[^\\s]*|[A-Za-z]:\\\\[^\\s]*)$"
          }
        },
        "allOf": [
          { 
            "if": { "properties": { "version": { "type": "string" } }, "required": ["version"] },
            "then": { "properties": { "ensure": { "const": "present" } } }
          },
          { 
            "if": { "properties": { "ensure": { "const": "absent" } }, "required": ["ensure"] },
            "then": { 
              "not": { "anyOf": [ { "required": ["version"] }, { "required": ["source"] } ] }
            }
          },
          { 
            "if": { "properties": { "manager": { "const": "apt" } }, "required": ["manager"] },
            "then": { },
            "else": { 
              "not": { "anyOf": [ { "required": ["configfiles"] }, { "required": ["mark_hold"] }, { "required": ["adminfile"] } ] }
            }
          },
          { 
            "if": { "properties": { "manager": { "enum": ["dnf", "yum"] } }, "required": ["manager"] },
            "then": { },
            "else": { "not": { "required": ["allow_downgrade"] } }
          },
          { 
            "if": { "properties": { "manager": { "const": "msi" } }, "required": ["manager"] },
            "then": { 
              "required": ["source"],
              "properties": { "source": { "pattern": "^(https?://[^\\s]+\\.msi|/[^\\s]+\\.msi|[A-Za-z]:\\\\[^\\s]+\\.msi)$" } }
            }
          }
        ]
      }
    }
,       "exec": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": False,
        "required": ["command"],
        "properties": {
          "command": {
            "type": "string",
            "minLength": 1,
            "pattern": ".*\\S.*",
            "default": ""
          },
          "creates": {
            "type": ["string","null"],
            "default": "",
            "pattern": "^(|/[^\\s]*|[A-Za-z]:\\\\[^\\s]*|https?://[^\\s]+)$"
          },
          "cwd": {
            "type": ["string","null"],
            "default": "",
            "pattern": "^(|/[^\\s]*|[A-Za-z]:\\\\[^\\s]*)$"
          },
          "environment": {
            "type": "array",
            "default": [],
            "uniqueItems": True,
            "items": {
              "type": "string",
              "pattern": "^[A-Z0-9_]+=.*$"
            }
          },
          "onlyif": { "type": ["string","null"], "default": "" },
          "unless": { "type": ["string","null"], "default": "" },
          "timeout": { "type": "integer", "default": 300, "minimum": 0, "maximum": 86400 },
          "tries": { "type": "integer", "default": 1, "minimum": 1, "maximum": 100 },
          "try_sleep": { "type": "integer", "default": 0, "minimum": 0, "maximum": 3600 },
          "umask": { "type": ["string","null"], "default": "", "pattern": "^(|[0-7]{3,4})$" },
          "user": {
            "type": "string",
            "default": "root",
            "pattern": "^[a-z_][a-z0-9_-]*[$]?$"
          }
        },
        "allOf": [
          {
            "not": { "required": ["onlyif", "unless"] }
          }
        ]
      }
    }
,       "ssh_config" : {
  "type": "object",
  "required": [
    "ssh_deletekeys",
    "ssh_genkeytypes",
    "ssh_quiet_keygen",
    "ssh_publish_hostkeys",
    "allow_public_ssh_keys",
    "disable_root",
    "disable_root_opts"
  ],
  "additionalProperties": False,
  "properties": {
    "ssh_deletekeys": { "type": "boolean", "default": True },

    "ssh_genkeytypes": {
      "type": "array",
      "default": ["ed25519", "rsa"],
      "minItems": 1,
      "uniqueItems": True,
      "items": { "type": "string", "enum": ["rsa", "ecdsa", "ed25519"] }
    },

    "ssh_quiet_keygen": { "type": "boolean", "default": False },

    "ssh_publish_hostkeys": {
      "type": "object",
      "required": ["enabled", "blacklist"],
      "additionalProperties": False,
      "properties": {
        "enabled": { "type": "boolean", "default": True },
        "blacklist": {
          "type": "array",
          "default": [],
          "uniqueItems": True,
          "items": { "type": "string", "enum": ["rsa", "ecdsa", "ed25519"] }
        }
      },
      "allOf": [
        {
          "if": { "properties": { "enabled": { "const": False } }, "required": ["enabled"] },
          "then": { "properties": { "blacklist": { "maxItems": 0 } } }
        }
      ]
    },

    "allow_public_ssh_keys": { "type": "boolean", "default": True },

    "disable_root": { "type": "boolean", "default": True },

    "disable_root_opts": {
      "type": "string",
      "default": "no-port-forwarding,no-agent-forwarding,no-X11-forwarding,command=\\\"echo Please login as the user \\\\\\\"$USER\\\\\\\" rather than \\\\\\\"$DISABLE_USER\\\\\\\";sleep 5;exit 142\\\"",
      "minLength": 0,
      "pattern": "^[^\\r\\n]*$"
    }
  },
  "allOf": [
    {
      "if": { "properties": { "disable_root": { "const": True } }, "required": ["disable_root"] },
      "then": { "properties": { "disable_root_opts": { "minLength": 1 } } }
    }
  ]
}
,       "bootcmd": {
          "type": "array",
          "minItems": 1,
          "items": {
            "anyOf": [
              { "type": "string", "minLength": 1 },               
              {
                "type": "array",                                  
                "minItems": 1,
                "items": { "type": "string", "minLength": 1 }
              }
            ]
          }
        }
,       "device_aliases": {
        "type": "object",
        "default": {},
        "patternProperties": {
          "^[a-zA-Z0-9_-]+$": { "type": "string", "pattern": "^/dev/[a-zA-Z0-9]+$" }
        },
        "additionalProperties": False
      },
      "disk_setup": {
        "type": "object",
        "default": {},
        "patternProperties": {
          "^(my_alias|swap_disk|/dev/[a-zA-Z0-9]+)$": {
            "type": "object",
            "required": ["layout", "overwrite", "table_type"],
            "additionalProperties": False,
            "properties": {
              "layout": {
                "oneOf": [
                  { "type": "boolean" },
                  {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                      "anyOf": [
                        { "type": "integer", "minimum": 1, "maximum": 100 },
                        {
                          "type": "array",
                          "minItems": 2,
                          "maxItems": 2,
                          "items": { "type": "integer", "minimum": 1 }
                        }
                      ]
                    }
                  }
                ]
              },
              "overwrite": { "type": "boolean" },
              "table_type": { "type": "string", "enum": ["mbr", "gpt"] }
            }
          }
        }
      },
      "fs_setup": {
        "type": "array",
        "default": [],
        "items": {
          "type": "object",
          "required": ["device", "filesystem", "label"],
          "additionalProperties": False,
          "properties": {
            "cmd": { "type": "string" },
            "device": { "type": "string" },
            "filesystem": { "type": "string", "enum": ["ext4", "xfs", "btrfs", "swap"] },
            "label": { "type": "string" }
          }
        }
      },
      "mount_default_fields": {
        "type": "array",
        "default": ["", "", "auto", "defaults,nofail", "0", "2"],
        "minItems": 6,
        "maxItems": 6
      },
      "mounts": {
        "type": "array",
        "default": [],
        "items": {
          "type": "array",
          "minItems": 2,
          "maxItems": 6,
          "items": { "type": ["string","null"] }
        }
      },
      "swap": {
        "type": "object",
        "required": ["filename", "size", "maxsize"],
        "additionalProperties": False,
        "properties": {
          "filename": { "type": "string", "pattern": "^[a-z_][a-z0-9_-]*$" },
          "size": { "type": "string", "pattern": "^[0-9]+[KMG]$" },
          "maxsize": { "type": "string", "pattern": "^[0-9]+[KMG]$" }
        }
      }            
,   "apt": {
    "type": "object",
    "required": ["primary", "security"],
    "additionalProperties": False,
    "properties": {
      "preserve_sources_list": { "type": "boolean", "default": False },

      "disable_suites": {
        "type": "array",
        "default": [],
        "uniqueItems": True,
        "items": {
          "type": "string",
          "enum": ["updates", "backports", "security", "proposed", "release"]
        }
      },

      "primary": {
        "type": "array",
        "minItems": 0,
        "items": {
          "type": "object",
          "required": ["arches", "uri"],
          "additionalProperties": False,
          "properties": {
            "arches": {
              "type": "array",
              "minItems": 1,
              "uniqueItems": True,
              "items": { "type": "string", "pattern": "^[A-Za-z0-9_-]+$" }
            },
            "uri": {
              "type": "string",
              "pattern": "^(https?|ftp|file)://[^\\s]+$"
            },
            "search": {
              "type": "array",
              "default": [],
              "items": { "type": "string", "minLength": 1 }
            },
            "search_dns": { "type": "boolean", "default": False },
            "keyid": { "type": "string", "pattern": "^[A-Fa-f0-9]{8,40}$" },
            "key": { "type": "string" },
            "keyserver": {
              "type": "string",
              "pattern": "^(hkp|hkps|https?)://[^\\s]+$"
            }
          }
        }
      },

      "security": {
        "type": "array",
        "minItems": 0,
        "items": {
          "type": "object",
          "required": ["arches", "uri"],
          "additionalProperties": False,
          "properties": {
            "arches": {
              "type": "array",
              "minItems": 1,
              "uniqueItems": True,
              "items": { "type": "string", "pattern": "^[A-Za-z0-9_-]+$" }
            },
            "uri": {
              "type": "string",
              "pattern": "^(https?|ftp|file)://[^\\s]+$"
            },
            "keyid": { "type": "string", "pattern": "^[A-Fa-f0-9]{8,40}$" },
            "keyserver": {
              "type": "string",
              "pattern": "^(hkp|hkps|https?)://[^\\s]+$"
            }
          }
        }
      },

      "http_proxy": { "type": "string", "pattern": "^http://[^\\s]+$" },
      "https_proxy": { "type": "string", "pattern": "^https?://[^\\s]+$" },
      "ftp_proxy": { "type": "string", "pattern": "^ftp://[^\\s]+$" },
      "proxy": { "type": "string", "pattern": "^(https?|ftp)://[^\\s]+$" },

      "debconf_selections": {
        "type": "object",
        "additionalProperties": { "type": "string" },
        "examples": [
          {
            "mysql-server": "mysql-server mysql-server/root_password password root123\\nmysql-server mysql-server/root_password_again password root123\\n"
          }
        ]
      },

      "sources": {
        "type": "object",
        "additionalProperties": False,
        "patternProperties": {
          "^.+$": {
            "type": "object",
            "required": ["source"],
            "additionalProperties": False,
            "properties": {
              "source": { "type": "string", "minLength": 1 },
              "keyid": { "type": "string", "pattern": "^[A-Fa-f0-9]{8,40}$" },
              "key": { "type": "string" },
              "keyserver": {
                "type": "string",
                "pattern": "^(hkp|hkps|https?)://[^\\s]+$"
              },
              "filename": {
                "type": "string",
                "pattern": "^(|/[^\\s]+)$"
              },
              "append": { "type": "boolean", "default": True }
            }
          }
        }
      },

      "conf": { "type": "string" }
    }
  }     
    }
}

def format_path(error) -> str:
    """
    Chuyển vị trí lỗi thành string dạng JSON Pointer-like.
    Ví dụ: files/0/type
    """
    parts = []
    for p in list(error.absolute_path):
        parts.append(str(p))
    return "/".join(parts) if parts else "(root)"

def collect_errors(instance) -> List[js_exceptions.ValidationError]:
    validator = Draft202012Validator(USER_DATA_SCHEMA)
    errors = sorted(validator.iter_errors(instance), key=lambda e: (list(e.absolute_path), e.message))
    return errors

def main():
    parser = argparse.ArgumentParser(description="Validate a JSON file against USER_DATA_SCHEMA.")
    parser.add_argument("json_path", help="Path to JSON file to validate")
    args = parser.parse_args()

    try:
        with open(args.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: file not found: {args.json_path}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON syntax at line {e.lineno}, col {e.colno}: {e.msg}", file=sys.stderr)
        sys.exit(2)

    errors = collect_errors(data)

    if not errors:
        print("✅ Valid JSON: conforms to USER_DATA_SCHEMA.")
        sys.exit(0)

    print(f"❌ Found {len(errors)} validation error(s):")
    for i, err in enumerate(errors, 1):
        path = format_path(err)
        print(f"\n[{i}] At: {path}")
        print(f"    Message: {err.message}")

        # Nếu có 'context' (các nhánh anyOf/oneOf/if/then), in ngắn gọn thêm
        if err.context:
            # Lấy vài thông điệp con ngắn gọn
            sub_msgs = sorted({c.message for c in err.context})
            for sm in sub_msgs[:5]:
                print(f"    Hint: {sm}")

    sys.exit(1)

if __name__ == "__main__":
    main()