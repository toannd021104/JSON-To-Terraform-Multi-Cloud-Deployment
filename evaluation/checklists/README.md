# Checklist Templates for Different VM Types

## Web Server (Apache/Nginx)

```json
{
  "checklist": [
    { "type": "package_installed", "target": "apache2" },
    { "type": "service_running", "target": "apache2" },
    { "type": "file_exists", "target": "/var/www/html/index.html" },
    {
      "type": "command_output",
      "command": "curl -s localhost",
      "expected": "Welcome"
    }
  ]
}
```

## Database Server (MySQL/PostgreSQL)

```json
{
  "checklist": [
    { "type": "package_installed", "target": "mysql-server" },
    { "type": "service_running", "target": "mysql" },
    { "type": "directory_exists", "target": "/var/lib/mysql" },
    {
      "type": "command_output",
      "command": "mysql --version",
      "expected": "mysql"
    }
  ]
}
```

## Docker Host

```json
{
  "checklist": [
    { "type": "package_installed", "target": "docker" },
    { "type": "service_running", "target": "docker" },
    {
      "type": "command_output",
      "command": "docker --version",
      "expected": "Docker version"
    },
    { "type": "user_exists", "target": "docker" }
  ]
}
```

## Basic Linux Configuration

```json
{
  "checklist": [
    { "type": "file_exists", "target": "/etc/hostname" },
    {
      "type": "command_output",
      "command": "hostname",
      "expected": "expected-hostname"
    },
    { "type": "network_connectivity", "target": "8.8.8.8" },
    { "type": "directory_exists", "target": "/home/ubuntu" }
  ]
}
```

## Custom Application

```json
{
  "checklist": [
    { "type": "file_exists", "target": "/opt/myapp/app.py" },
    { "type": "directory_exists", "target": "/var/log/myapp" },
    { "type": "service_running", "target": "myapp" },
    {
      "type": "command_output",
      "command": "ps aux | grep myapp",
      "expected": "python"
    }
  ]
}
```
