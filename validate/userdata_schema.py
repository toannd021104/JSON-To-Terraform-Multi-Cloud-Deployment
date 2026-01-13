#!/usr/bin/env python3
import argparse
import json
import sys
from jsonschema import Draft202012Validator, exceptions as js_exceptions
from typing import List, Dict, Callable


# Schema definition for validating user data JSON
USER_DATA_SCHEMA = {
  "type": "object",
  "required": ["target"],
  "additionalProperties": False,
  "properties": {
    "target": {
      "type": "string",
      "enum": ["windows", "wins", "wind", "winserver", "linux", "lin", "lnx", "unix"],
      "description": "Target operating system"
    },
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
            "pattern": "^(/[^\n]+|[A-Za-z]:\\\\[^\n]+)$"
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
            "pattern": "^[a-z_][a-z0-9_-]*:[a-z_][a-z0-9_-]*$"
          },
          "mode": {
            "type": "string",
            "default": "0644",
            "pattern": "^[0-7]{3,4}$"
          },
          "source": {
            "oneOf": [
              {
                "type": "string",
                "minLength": 1
              },
              {
                "type": "null"
              }
            ]
          },
          "target": {
            "type": ["string", "null"],
            "default": "",
            "pattern": "^(/[^\n]+|[A-Za-z]:\\\\[^\n]+)$"
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
          },
          "encoding": {
            "type": "string",
            "enum": [
              "gz",
              "gzip",
              "gz+base64",
              "gzip+base64",
              "gz+b64",
              "gzip+b64",
              "b64",
              "base64",
              "text/plain"
            ],
            "default": "text/plain",
            "description": "Encoding type of the content"
          }
        },
        "allOf": [
          {
            "if": {
              "properties": {
                "type": {
                  "const": "file"
                }
              },
              "required": ["type"]
            },
            "then": {
              "not": {
                "required": ["target"]
              },
              "allOf": [
                {
                  "anyOf": [{"required": ["content"]}, {"required": ["source"]}]
                }
              ]
            }
          },
          {
            "if": {
              "properties": {
                "type": {
                  "const": "dir"
                }
              },
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
                "mode": {
                  "pattern": "^[0-7]{3,4}$"
                }
              }
            }
          },
          {
            "if": {
              "properties": {
                "type": {
                  "const": "link"
                }
              },
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
                "mode": {
                  "pattern": "^[0-7]{3,4}$"
                }
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
          {
            "const": "default"
          },
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
              "gecos": {
                "type": ["string", "null"],
                "default": ""
              },
              "primary_group": {
                "type": ["string", "null"],
                "default": "",
                "pattern": "^[a-zA-Z_][a-zA-Z0-9_ -]*$"
              },
              "groups": {
                "oneOf": [
                  {
                    "type": "string",
                    "minLength": 1,
                    "pattern": "^[a-zA-Z_][a-zA-Z0-9_-]*$"
                  },
                  {
                    "type": "array",
                    "items": {
                      "type": "string",
                      "minLength": 1,
                      "pattern": "^[a-zA-Z_][a-zA-Z0-9_-]*$"
                    },
                    "uniqueItems": True
                  },
                  {
                    "type": "object",
                    "properties": {
                      "name": {
                        "type": "string",
                        "minLength": 1
                      },
                      "gid": {
                        "type": "integer",
                        "minimum": 0
                      }
                    },
                    "required": [
                      "name"
                    ],
                    "additionalProperties": False
                  }
                ]
              },
              "shell": {
                "type": ["string", "null"],
                "default": "",
                "pattern": "^/[^\\s]*$"
              },
              "uid": {
                "type": ["integer", "null"],
                "default": "",
                "minimum": 0,
                "maximum": 60000
              },
              "system": {
                "type": "boolean",
                "default": False
              },
              "lock_passwd": {
                "type": "boolean",
                "default": False
              },
              "expiredate": {
                "type": ["string", "null"],
                "default": "",
                "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
              },
              "create_groups": {
                "type": "boolean",
                "default": False
              },
              "hashed_passwd": {
                "type": ["string", "null"],
                "default": ""
              },
              "plain_passwd": {
                "type": ["string", "null"],
                "default": ""
              },
              "ssh_authorized_keys": {
                "type": "array",
                "default": [],
                "items": {
                  "type": "string",
                  "minLength": 20,
                  "pattern": "^(ssh-(rsa|dss|ed25519)|ecdsa-sha2-nistp(256|384|521)) [A-Za-z0-9+/=]+( .+)?$"
                }
              },
              "sudo": {
                "type": ["string", "null"],
                "default": ""
              },
              "password_policy": {
                "type": "object",
                "default": {},
                "additionalProperties": False,
                "properties": {
                  "max_days": {
                    "type": ["integer", "null"],
                    "default": 90,
                    "minimum": 0
                  },
                  "min_days": {
                    "type": ["integer", "null"],
                    "default": 7,
                    "minimum": 0
                  },
                  "warn_days": {
                    "type": ["integer", "null"],
                    "default": 7,
                    "minimum": 0
                  }
                }
              },
              "no_create_home": {
                "type": "boolean",
                "default": False
              },
              "no_user_group": {
                "type": "boolean",
                "default": False
              },
              "inactive": {
                "oneOf": [
                  {
                    "type": "string",
                    "pattern": "^[0-9]+$",
                    "description": "Number of days until user is disabled (Linux cloud-init)"
                  },
                  {
                    "type": "boolean",
                    "description": "Disable user account immediately (Windows cloudbase-init)"
                  }
                ],
                "description": "Linux: number of days until disabled (e.g., '30'). Windows: true/false to disable account."
              },
              "passwd": {
                "oneOf": [
                  {
                    "type": "string",
                    "pattern": "^\\$[1-6y]\\$.+\\$.+$",
                    "description": "Hashed password (SHA-512, SHA-256, etc.)"
                  },
                  {
                    "type": "string",
                    "minLength": 1,
                    "description": "Plain text password (will be hashed automatically)"
                  }
                ]
              }
            },
            "allOf": [
              {
                "if": {
                  "properties": {
                    "system": {
                      "const": True
                    }
                  },
                  "required": ["system"]
                },
                "then": {
                  "properties": {
                    "uid": {
                      "type": ["integer", "null"],
                      "maximum": 999
                    }
                  }
                }
              },
              {
                "if": {
                  "properties": {
                    "system": {
                      "const": False
                    }
                  },
                  "required": ["system"]
                },
                "then": {
                  "properties": {
                    "uid": {
                      "type": ["integer", "null"],
                      "minimum": 1000
                    }
                  }
                }
              },
              {
                "not": {
                  "required": ["hashed_passwd", "plain_passwd"]
                }
              },
              {
                "if": {
                  "properties": {
                    "lock_passwd": {
                      "const": True
                    }
                  },
                  "required": ["lock_passwd"]
                },
                "then": {
                  "not": {
                    "anyOf": [{"required": ["hashed_passwd"]}, {"required": ["plain_passwd"]}]
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
              "properties": {
                "provider": {
                  "const": "systemd"
                }
              },
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
              "properties": {
                "provider": {
                  "const": "windows"
                }
              },
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
        "required": ["name"],
        "properties": {
          "name": {
            "type": "string",
            "minLength": 1,
            "pattern": "^[A-Za-z0-9._+:-]+$"
          },
          "ensure": {
            "type": "string",
            "pattern": "^(present|latest|absent|(\\d+:)?[\\d\\.\\+\\~]+.*)$",
            "description": "Package state (present/latest/absent) or apt version string"
          },
          "version": {
            "type": "string",
            "minLength": 1
          },
          "options": {
            "type": "array",
            "items": {
              "type": "string",
              "minLength": 1
            }
          },
          "mark_hold": {
            "type": "boolean"
          }
        },
        "allOf": [
          {
            "if": {
              "properties": {
                "ensure": {
                  "const": "absent"
                }
              }
            },
            "then": {
              "not": {
                "anyOf": [{"required": ["version"]}, {"required": ["mark_hold"]}]
              }
            }
          },
          {
            "if": {
              "required": ["version"]
            },
            "then": {
              "properties": {
                "ensure": {
                  "const": "present"
                }
              }
            }
          }
        ]
      }
    },
    "exec": {
      "type": "array",
      "minItems": 1,
      "items": {
        "oneOf": [
          {
            "type": "string",
            "minLength": 1,
            "description": "Simple command string"
          },
          {
            "type": "object",
            "additionalProperties": False,
            "required": ["command"],
            "properties": {
              "command": {
                "type": "string",
                "minLength": 1,
                "pattern": ".*\\S.*"
              },
              "creates": {
                "type": ["string", "null"],
                "default": ""
              },
              "cwd": {
                "type": ["string", "null"],
                "default": ""
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
              "onlyif": {
                "type": ["string", "null"],
                "default": ""
              },
              "unless": {
                "type": ["string", "null"],
                "default": ""
              },
              "timeout": {
                "type": "integer",
                "default": 300,
                "minimum": 0,
                "maximum": 86400
              },
              "tries": {
                "type": "integer",
                "default": 1,
                "minimum": 1,
                "maximum": 100
              },
              "try_sleep": {
                "type": "integer",
                "default": 0,
                "minimum": 0,
                "maximum": 3600
              },
              "umask": {
                "type": ["string", "null"],
                "default": ""
              },
              "user": {
                "type": "string",
                "default": "root",
                "pattern": "^[a-z_][a-z0-9_-]*[$]?$"
              }
            },
            "allOf": [
              {
                "not": {
                  "required": ["onlyif", "unless"]
                }
              }
            ]
          }
        ]
      }
    },
    "ssh_config": {
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
        "ssh_deletekeys": {
          "type": "boolean",
          "default": True
        },
        "ssh_genkeytypes": {
          "type": "array",
          "default": ["ed25519", "rsa"],
          "minItems": 1,
          "uniqueItems": True,
          "items": {
            "type": "string",
            "enum": ["rsa", "ecdsa", "ed25519"]
          }
        },
        "ssh_quiet_keygen": {
          "type": "boolean",
          "default": False
        },
        "ssh_publish_hostkeys": {
          "type": "object",
          "required": ["enabled", "blacklist"],
          "additionalProperties": False,
          "properties": {
            "enabled": {
              "type": "boolean",
              "default": True
            },
            "blacklist": {
              "type": "array",
              "default": [],
              "uniqueItems": True,
              "items": {
                "type": "string",
                "enum": ["rsa", "ecdsa", "ed25519"]
              }
            }
          },
          "allOf": [
            {
              "if": {
                "properties": {
                  "enabled": {
                    "const": False
                  }
                },
                "required": ["enabled"]
              },
              "then": {
                "properties": {
                  "blacklist": {
                    "maxItems": 0
                  }
                }
              }
            }
          ]
        },
        "allow_public_ssh_keys": {
          "type": "boolean",
          "default": True
        },
        "disable_root": {
          "type": "boolean",
          "default": True
        },
        "disable_root_opts": {
          "type": "string",
          "default": "no-port-forwarding,no-agent-forwarding,no-X11-forwarding,command=\\\"echo Please login as the user \\\\\\\"$USER\\\\\\\" rather than \\\\\\\"$DISABLE_USER\\\\\\\";sleep 5;exit 142\\\"",
          "minLength": 0,
          "pattern": "^[^\\r\\n]*$"
        }
      },
      "allOf": [
        {
          "if": {
            "properties": {
              "disable_root": {
                "const": True
              }
            },
            "required": ["disable_root"]
          },
          "then": {
            "properties": {
              "disable_root_opts": {
                "minLength": 1
              }
            }
          }
        }
      ]
    },
    "bootcmd": {
      "type": "array",
      "minItems": 1,
      "items": {
        "anyOf": [
          {
            "type": "string",
            "minLength": 1
          },
          {
            "type": "array",
            "minItems": 1,
            "items": {
              "type": "string",
              "minLength": 1
            }
          }
        ]
      }
    },
    "device_aliases": {
      "type": "object",
      "default": {},
      "patternProperties": {
        "^[a-zA-Z0-9_-]+$": {
          "type": "string",
          "pattern": "^/dev/[a-zA-Z0-9]+$"
        }
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
                {
                  "type": "boolean"
                },
                {
                  "type": "array",
                  "minItems": 1,
                  "items": {
                    "anyOf": [
                      {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100
                      },
                      {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 2,
                        "items": {
                          "type": "integer",
                          "minimum": 1
                        }
                      }
                    ]
                  }
                }
              ]
            },
            "overwrite": {
              "type": "boolean"
            },
            "table_type": {
              "type": "string",
              "enum": ["mbr", "gpt"]
            }
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
          "cmd": {
            "type": "string"
          },
          "device": {
            "type": "string"
          },
          "filesystem": {
            "type": "string",
            "enum": ["ext4", "xfs", "btrfs", "swap"]
          },
          "label": {
            "type": "string"
          }
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
        "items": {
          "type": ["string", "null"]
        }
      }
    },
    "swap": {
      "type": "object",
      "required": ["filename", "size", "maxsize"],
      "additionalProperties": False,
      "properties": {
        "filename": {
          "type": "string",
          "pattern": "^/[^\\s]*$"
        },
        "size": {
          "type": "string",
          "pattern": "^[0-9]+[KMG]$"
        },
        "maxsize": {
          "type": "string",
          "pattern": "^[0-9]+[KMG]$"
        }
      }
    },
    "apt": {
      "type": "object",
      "required": ["primary", "security"],
      "additionalProperties": False,
      "properties": {
        "preserve_sources_list": {
          "type": "boolean",
          "default": False
        },
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
                "items": {
                  "type": "string",
                  "pattern": "^[A-Za-z0-9_-]+$"
                }
              },
              "uri": {
                "type": "string",
                "pattern": "^(https?|ftp|file)://[^\\s]+$"
              },
              "search": {
                "type": "array",
                "default": [],
                "items": {
                  "type": "string",
                  "minLength": 1
                }
              },
              "search_dns": {
                "type": "boolean",
                "default": False
              },
              "keyid": {
                "type": "string",
                "pattern": "^[A-Fa-f0-9]{8,40}$"
              },
              "key": {
                "type": "string"
              },
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
                "items": {
                  "type": "string",
                  "pattern": "^[A-Za-z0-9_-]+$"
                }
              },
              "uri": {
                "type": "string",
                "pattern": "^(https?|ftp|file)://[^\\s]+$"
              },
              "keyid": {
                "type": "string",
                "pattern": "^[A-Fa-f0-9]{8,40}$"
              },
              "keyserver": {
                "type": "string",
                "pattern": "^(hkp|hkps|https?)://[^\\s]+$"
              }
            }
          }
        },
        "http_proxy": {
          "type": "string",
          "pattern": "^http://[^\\s]+$"
        },
        "https_proxy": {
          "type": "string",
          "pattern": "^https?://[^\\s]+$"
        },
        "ftp_proxy": {
          "type": "string",
          "pattern": "^ftp://[^\\s]+$"
        },
        "proxy": {
          "type": "string",
          "pattern": "^(https?|ftp)://[^\\s]+$"
        },
        "debconf_selections": {
          "type": "object",
          "additionalProperties": {
            "type": "string"
          },
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
                "source": {
                  "type": "string",
                  "minLength": 1
                },
                "keyid": {
                  "type": "string",
                  "pattern": "^[A-Fa-f0-9]{8,40}$"
                },
                "key": {
                  "type": "string"
                },
                "keyserver": {
                  "type": "string",
                  "pattern": "^(hkp|hkps|https?)://[^\\s]+$"
                },
                "filename": {
                  "type": "string",
                  "pattern": "^(|/[^\\s]+)$"
                },
                "append": {
                  "type": "boolean",
                  "default": True
                }
              }
            }
          }
        },
        "conf": {
          "type": "string"
        }
      }
    },
    "growpart": {
      "type": "object",
      "properties": {
        "mode": {
          "type": "string",
          "enum": ["auto", "growpart", "gpart", "off"],
          "default": "auto"
        },
        "devices": {
          "type": "array",
          "minItems": 1,
          "uniqueItems": True,
          "items": {
            "type": "string",
            "pattern": "^/(?:[a-zA-Z0-9/_-]*)?$",
            "default": "/"
          },
          "default": ["/"]
        },
        "ignore_growroot_disabled": {
          "type": "boolean",
          "default": False
        }
      },
      "additionalProperties": False,
      "default": {
        "mode": "auto",
        "devices": ["/"],
        "ignore_growroot_disabled": False
      }
    },
    "resize_rootfs": {
      "type": "boolean",
      "default": True
    },
    "ntp": {
      "type": "object",
      "properties": {
        "enabled": {
          "type": "boolean",
          "default": True
        },
        "ntp_client": {
          "type": "string",
          "enum": ["auto", "chrony", "ntp", "openntpd", "ntpdate", "systemd-timesyncd"],
          "default": "auto"
        },
        "servers": {
          "type": "array",
          "minItems": 0,
          "uniqueItems": True,
          "items": {
            "type": "string",
            "pattern": "^(?!\\s*$).+"
          },
          "default": []
        },
        "pools": {
          "type": "array",
          "minItems": 0,
          "uniqueItems": True,
          "items": {
            "type": "string",
            "pattern": "^(?!\\s*$).+"
          },
          "default": []
        },
        "peers": {
          "type": "array",
          "minItems": 0,
          "uniqueItems": True,
          "items": {
            "type": "string",
            "pattern": "^(?!\\s*$).+"
          },
          "default": []
        },
        "allow": {
          "type": "array",
          "minItems": 0,
          "uniqueItems": True,
          "items": {
            "type": "string",
            "pattern": "^([0-9]{1,3}\\.){3}[0-9]{1,3}(/[0-9]{1,2})?$"
          },
          "default": []
        },
        "config": {
          "type": "object",
          "properties": {
            "confpath": {
              "type": "string",
              "pattern": "^/(?:[a-zA-Z0-9._/-]+)+$",
              "default": "/etc/chrony/chrony.conf"
            },
            "check_exe": {
              "type": "string",
              "pattern": "^[a-zA-Z0-9._-]+$",
              "default": "chronyd"
            },
            "packages": {
              "type": "array",
              "minItems": 1,
              "uniqueItems": True,
              "items": {
                "type": "string",
                "pattern": "^[a-zA-Z0-9._+-]+$"
              },
              "default": ["chrony"]
            },
            "service_name": {
              "type": "string",
              "pattern": "^[a-zA-Z0-9._-]+$",
              "default": "chronyd"
            },
            "template": {
              "type": "string",
              "minLength": 1
            }
          },
          "additionalProperties": False,
          "default": {
            "confpath": "/etc/chrony/chrony.conf",
            "check_exe": "chronyd",
            "packages": ["chrony"],
            "service_name": "chronyd"
          }
        }
      },
      "additionalProperties": False,
      "default": {
        "enabled": True,
        "ntp_client": "auto",
        "servers": [],
        "pools": [],
        "peers": [],
        "allow": []
      }
    },
    "power_state": {
      "type": "object",
      "properties": {
        "delay": {
          "oneOf": [
            {
              "type": "integer",
              "minimum": 0
            },
            {
              "type": "string",
              "enum": ["now"]
            }
          ],
          "default": "now"
        },
        "mode": {
          "type": "string",
          "enum": ["poweroff", "halt", "reboot"],
          "default": "reboot"
        },
        "message": {
          "type": "string",
          "default": "Rebooting to apply updates..."
        },
        "timeout": {
          "type": "integer",
          "minimum": 0,
          "default": 30
        },
        "condition": {
          "oneOf": [
            {
              "type": "boolean"
            },
            {
              "type": "string",
              "minLength": 1
            },
            {
              "type": "array",
              "items": {
                "type": "string",
                "minLength": 1
              },
              "minItems": 1
            }
          ],
          "default": True
        }
      },
      "required": ["mode"],
      "additionalProperties": False
    },
    "package_reboot_if_required": {
      "type": "boolean",
      "default": False
    },
    "package_update": {
      "type": "boolean",
      "default": False
    },
    "package_upgrade": {
      "type": "boolean",
      "default": False
    },
    "hostname": {
      "type": "string",
      "default": "",
      "minLength": 1,
      "maxLength": 63,
      "pattern": "^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$"
    },
    "preserve_hostname": {
      "type": "boolean",
      "default": False
    },
    "create_hostname_file": {
      "type": "boolean",
      "default": True
    },
    "fqdn": {
      "type": "string",
      "default": "",
      "minLength": 1,
      "maxLength": 253,
      "pattern": "^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\\.)+[a-z]{2,}$"
    },
    "prefer_fqdn_over_hostname": {
      "type": "boolean",
      "default": False
    },
    "manage_etc_hosts": {
      "oneOf": [
        {
          "type": "boolean"
        },
        {
          "type": "string",
          "enum": ["template", "localhost"]
        }
      ],
      "default": False
    },
    "timezone": {
      "type": "string",
      "minLength": 1,
      "pattern": "^[A-Za-z_]+/[A-Za-z_]+(?:/[A-Za-z_]+)*$",
      "examples": ["Asia/Ho_Chi_Minh", "America/New_York"]
    },
    "locale": {
      "type": "string",
      "minLength": 2,
      "pattern": "^[A-Za-z]{2}_[A-Za-z]{2}\\.UTF-8$",
      "examples": ["en_US.UTF-8", "vi_VN.UTF-8"]
    }
  },
  "allOf": [
    {
      "if": {
        "properties": {
          "target": {
            "enum": ["windows", "wins", "wind", "winserver"]
          }
        }
      },
      "then": {
        "anyOf": [
          {"required": ["files"]},
          {"required": ["timezone"]},
          {"required": ["hostname"]},
          {"required": ["ntp"]},
          {"required": ["users"]},
          {"required": ["groups"]},
          {"required": ["runcmd"]},
          {"required": ["package"]}
        ]
      }
    },
    {
      "if": {
        "properties": {
          "target": {
            "enum": ["linux"]
          }
        }
      },
      "then": {
      }
    }
  ]
}
 
 
ERROR_MESSAGES: Dict[str, Callable] = {
    'required': lambda err: f"Missing required field: '{list(err.validator_value)[0]}'. Please add this field to your configuration.",
    'enum': lambda err: f"Invalid value '{err.instance}'. Allowed values are: {', '.join(map(str, err.validator_value))}",
    'type': lambda err: f"Expected type '{err.validator_value}', got '{type(err.instance).__name__}' (value: '{err.instance}')",
    'pattern': lambda err: f"Value '{err.instance}' does not match required pattern: {err.validator_value}",
    'minLength': lambda err: f"Value '{err.instance}' is too short. Minimum length: {err.validator_value}",
    'minimum': lambda err: f"Value '{err.instance}' is too small. Minimum: {err.validator_value}",
    'maximum': lambda err: f"Value '{err.instance}' is too large. Maximum: {err.validator_value}",
}

# Field-specific custom messages (optional, mở rộng thêm)
FIELD_SPECIFIC_MESSAGES: Dict[str, Dict[str, str]] = {
    'target': {
        'required': "Field 'target' is required. Please specify: 'windows' or 'linux'.",
        'enum': "Invalid target OS. Must be either 'windows' or 'linux'."
    },
    'passwd': {
        'pattern': "Password must be in hashed format (SHA-512) or plain text. Use: mkpasswd --method=SHA-512"
    },
    'ssh_authorized_keys': {
        'pattern': "Invalid SSH key format. Expected: 'ssh-rsa|ssh-ed25519 <base64_key> [comment]'"
    }
}

def format_path(error: js_exceptions.ValidationError) -> str:
    """Format error path for display"""
    if not error.absolute_path:
        return "(root)"
    return "/".join(str(p) for p in error.absolute_path)

def get_custom_message(error: js_exceptions.ValidationError) -> str:
    """Get custom error message or fallback to default"""
    # Get field name from path
    field_name = str(error.absolute_path[-1]) if error.absolute_path else None
    
    # Check field-specific messages first
    if field_name and field_name in FIELD_SPECIFIC_MESSAGES:
        field_messages = FIELD_SPECIFIC_MESSAGES[field_name]
        if error.validator in field_messages:
            return field_messages[error.validator]
    
    # Check generic validator messages
    if error.validator in ERROR_MESSAGES:
        try:
            return ERROR_MESSAGES[error.validator](error)
        except Exception:
            pass
    
    # Fallback to original message
    return error.message

def collect_errors(instance) -> List[js_exceptions.ValidationError]:
    validator = Draft202012Validator(USER_DATA_SCHEMA)
    errors = sorted(validator.iter_errors(instance), key=lambda e: (list(e.absolute_path), e.message))
    return errors

def validate(json_path: str) -> bool:
    """
    Validate a JSON file against USER_DATA_SCHEMA.
    
    Args:
        json_path: Path to JSON file to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: file not found: {json_path}", file=sys.stderr)
        return False
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON syntax at line {e.lineno}, col {e.colno}: {e.msg}", file=sys.stderr)
        return False

    errors = collect_errors(data)

    if not errors:
        print("✓ Valid JSON: conforms to USER_DATA_SCHEMA.")
        return True

    print(f"✗ Found {len(errors)} validation error(s):")
    for i, err in enumerate(errors, 1):
        path = format_path(err)
        custom_msg = get_custom_message(err)
        
        print(f"\n[{i}] At: {path}")
        print(f"    Error: {custom_msg}")
        # print(f"    Value: {repr(err.instance)}")

        # Show original message if different
        if custom_msg != err.message:
            print(f"    Detail: {err.message}")

        # Show context hints
        if err.context:
            sub_msgs = sorted({get_custom_message(c) for c in err.context})
            for sm in sub_msgs[:3]:  # Limit to 3 hints
                print(f"    Hint: {sm}")

    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate a JSON file against USER_DATA_SCHEMA.")
    parser.add_argument("json_path", help="Path to JSON file to validate")
    args = parser.parse_args()
    
    is_valid = validate(args.json_path)
    sys.exit(0 if is_valid else 1)