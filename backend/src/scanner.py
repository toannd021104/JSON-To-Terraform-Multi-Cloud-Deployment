import os
from pathlib import Path
from typing import List, Dict
    # Quét thư mục (mặc định là .)
def scan_projects(base_path: str = "/app/terraform-projects") -> list[dict]:
    projects = [] # Danh sách các folder
        # Với từng thư mục con trong thư mục gốc
    for entry in os.listdir(base_path):
        entry_path = Path(base_path) / entry
        
        # Kiểm tra nếu là thư mục và có dạng "aws_" hoặc "openstack_" ở đầu
        if entry_path.is_dir() and (entry.startswith("aws_") or entry.startswith("openstack_")):
            project_type = "aws" if entry.startswith("aws_") else "openstack"
            
            # Tìm các thư mục con bên trong
            children = [
                child.name for child in entry_path.iterdir() 
                if child.is_dir() and child.name.startswith(f"{project_type}_")
            ]
            
            projects.append({
                "type": project_type,
                "parent": entry,
                "children": children
            })
    
    return projects

if __name__ == "__main__":
    # Chạy quét thư mục
    projects = scan_projects()
    print(projects)