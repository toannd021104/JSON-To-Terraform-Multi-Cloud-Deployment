import os
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

def run_command(folder, command):
    try:
        print(f"\n Đang xử lý {folder.name}...")
        
        # Lưu thư mục hiện tại
        #original_dir = os.getcwd()
        
        # Chuyển đến thư mục cần xử lý
        os.chdir(str(folder.absolute()))
        
        if command == "init":
            exit_code = os.system(f"terraform {command}")
        else:
            exit_code = os.system(f"terraform {command} -auto-approve")
            
        if exit_code != 0:
            print(f" Lỗi trong {folder.name}")
        
        # Trở về thư mục ban đầu
        #os.chdir(original_dir)
        return exit_code
    except Exception as e:
        print(f" Lỗi khi xử lý {folder}: {str(e)}")
        return 1

def run_parallel(command):
    # Lấy thư mục hiện tại
    current_dir = Path.cwd()
    
    # Tìm tất cả thư mục con (openstack hoặc aws)
    folders = [d for d in current_dir.iterdir() if d.is_dir() and 
              (d.name.startswith("openstack_") or d.name.startswith("aws_"))]
    
    if not folders:
        print(f"Không tìm thấy thư mục nào bắt đầu bằng 'openstack_' hoặc 'aws_' trong {current_dir}")
        return
    
    print(f"Tìm thấy {len(folders)} thư mục để xử lý:")
    for folder in folders:
        print(f" - {folder.name}")
    
    with ThreadPoolExecutor() as executor:
        results = list(executor.map(lambda f: run_command(f, command), folders))
    
    success = results.count(0)
    print(f"\n Kết quả: {success}/{len(folders)} thành công")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python run_terraform.py [init|apply|destroy]")
        sys.exit(1)
    
    command = sys.argv[1]
    if command not in ["init", "apply", "destroy"]:
        print("Chỉ hỗ trợ: init, apply, destroy")
        sys.exit(1)
    
    run_parallel(command)