#!/usr/bin/env python3
"""
Kịch bản 2: Đánh giá khả năng mở rộng và nhân bản hạ tầng

Sử dụng:
    python3 scenario2_scalability.py                           # Mặc định N=1,3,5
    python3 scenario2_scalability.py 1,3,5,10,20              # Tự chọn N
    python3 scenario2_scalability.py 1,3,5,10,20,40,60,100    # Full test

Kết quả:
    - Thời gian generate
    - Thời gian terraform apply  
    - Số trùng tên tài nguyên
    - Tính nhất quán cấu trúc
"""

import os
import sys
import json
import time
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import re

# Paths
SCRIPT_DIR = Path(__file__).parent.absolute()
EVALUATION_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = EVALUATION_DIR.parent
TERRAFORM_GENERATOR = PROJECT_ROOT / "terraform-generator"
TERRAFORM_PROJECTS = PROJECT_ROOT / "terraform-projects"


def log(message: str):
    """In log với timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")


def run_command(cmd: List[str], cwd: str = None, timeout: int = 1800) -> Tuple[int, str, str, float]:
    """Chạy command và đo thời gian"""
    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout
        )
        elapsed = time.time() - start_time
        return result.returncode, result.stdout, result.stderr, elapsed
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        return -1, "", "Timeout", elapsed
    except Exception as e:
        elapsed = time.time() - start_time
        return -1, "", str(e), elapsed


def cleanup_terraform_projects():
    """Dọn dẹp tất cả terraform projects"""
    if TERRAFORM_PROJECTS.exists():
        for item in TERRAFORM_PROJECTS.iterdir():
            if item.is_dir() and item.name.startswith("openstack_"):
                try:
                    # Destroy trước khi xóa
                    for sub in item.iterdir():
                        if sub.is_dir() and sub.name.startswith("openstack_"):
                            tfstate = sub / "terraform.tfstate"
                            if tfstate.exists():
                                subprocess.run(
                                    ["terraform", "destroy", "-auto-approve", "-no-color"],
                                    cwd=str(sub),
                                    capture_output=True,
                                    timeout=300
                                )
                    shutil.rmtree(item)
                except Exception as e:
                    log(f"  Warning: Không thể xóa {item}: {e}")


def copy_topology_to_generator(topology_file: Path) -> Path:
    """Copy topology file vào terraform-generator"""
    dest = TERRAFORM_GENERATOR / "topology.json"
    shutil.copy(topology_file, dest)
    return dest


def run_generate_with_copies(n: int) -> Dict:
    """
    Chạy generate.py với N bản sao
    
    Command: python3 generate.py openstack N
    """
    result = {
        "n": n,
        "generate_time": 0,
        "apply_time": 0,
        "total_time": 0,
        "resources": 0,
        "success": False,
        "folders_created": 0,
        "errors": [],
        "name_duplicates": 0,
        "structure_consistent": True
    }
    
    log(f"  Chạy generate.py openstack {n}...")
    
    # Chạy generate.py openstack N
    start_time = time.time()
    cmd = ["python3", "generate.py", "openstack", str(n)]
    
    returncode, stdout, stderr, elapsed = run_command(
        cmd,
        cwd=str(TERRAFORM_GENERATOR),
        timeout=3600  # 1 giờ cho N lớn
    )
    
    result["generate_time"] = elapsed
    
    if returncode != 0:
        result["errors"].append(f"Generate failed: {stderr[:500]}")
        result["total_time"] = elapsed
        return result
    
    # Đếm resources từ output "Total: X added" hoặc tổng các dòng "Added"
    # Tìm dòng "Total: X added, Y changed, Z destroyed"
    total_match = re.search(r"Total:\s*(\d+)\s*added", stdout)
    if total_match:
        result["resources"] = int(total_match.group(1))
    else:
        # Fallback: tổng tất cả "X added" trong output
        total_added = 0
        for match in re.finditer(r"(\d+)\s+added", stdout):
            total_added += int(match.group(1))
        result["resources"] = total_added
    
    # Tìm số folders thành công
    match = re.search(r"(\d+) folder\(s\) succeeded", stdout)
    if match:
        result["folders_created"] = int(match.group(1))
    else:
        # Đếm từ terraform-projects
        result["folders_created"] = count_created_folders()
    
    # Kiểm tra success
    result["success"] = ("Success" in stdout or "✓" in stdout) and returncode == 0
    
    # Tính thời gian apply từ output hoặc ước tính
    # generate.py đã tự động apply, nên total_time = generate_time
    result["apply_time"] = elapsed
    result["total_time"] = elapsed
    
    # Kiểm tra trùng tên và tính nhất quán
    check_duplicates_and_consistency(result)
    
    return result


def count_created_folders() -> int:
    """Đếm số folders được tạo trong terraform-projects"""
    count = 0
    if TERRAFORM_PROJECTS.exists():
        for item in TERRAFORM_PROJECTS.iterdir():
            if item.is_dir() and item.name.startswith("openstack_"):
                for sub in item.iterdir():
                    if sub.is_dir() and sub.name.startswith("openstack_"):
                        count += 1
    return count


def count_real_resources() -> int:
    """Đếm số resources thực sự từ state files (chỉ đếm resources có instances thực sự)"""
    total = 0
    if not TERRAFORM_PROJECTS.exists():
        return 0
    
    for item in TERRAFORM_PROJECTS.iterdir():
        if not (item.is_dir() and item.name.startswith("openstack_")):
            continue
        for sub in item.iterdir():
            if not (sub.is_dir() and sub.name.startswith("openstack_")):
                continue
            tfstate = sub / "terraform.tfstate"
            if not tfstate.exists():
                continue
            try:
                with open(tfstate) as f:
                    state = json.load(f)
                for res in state.get("resources", []):
                    # Chỉ đếm resources có instances thực sự (không rỗng)
                    instances = res.get("instances", [])
                    for inst in instances:
                        attrs = inst.get("attributes") or {}
                        # Bỏ qua resource chưa tạo (id null/empty)
                        if not attrs or not attrs.get("id"):
                            continue
                        total += 1
            except Exception:
                pass
    return total


def check_duplicates_and_consistency(result: Dict):
    """Kiểm tra trùng tên tài nguyên và tính nhất quán cấu trúc"""
    if not TERRAFORM_PROJECTS.exists():
        return
    
    # Thu thập tất cả tên tài nguyên
    all_names = set()
    name_duplicates = 0
    structures = []
    
    for item in TERRAFORM_PROJECTS.iterdir():
        if not (item.is_dir() and item.name.startswith("openstack_")):
            continue
            
        for sub in item.iterdir():
            if not (sub.is_dir() and sub.name.startswith("openstack_")):
                continue
                
            tfstate = sub / "terraform.tfstate"
            if not tfstate.exists():
                continue
            
            try:
                with open(tfstate) as f:
                    state = json.load(f)
                
                structure = {"networks": 0, "instances": 0, "routers": 0}
                
                for res in state.get("resources", []):
                    res_type = res.get("type", "")
                    
                    for inst in res.get("instances", []):
                        attrs = inst.get("attributes", {})
                        
                        # Kiểm tra trùng tên
                        name = attrs.get("name", "")
                        if name:
                            if name in all_names:
                                name_duplicates += 1
                            all_names.add(name)
                        
                        # Đếm cấu trúc
                        if "network" in res_type and "subnet" not in res_type:
                            structure["networks"] += 1
                        elif "compute_instance" in res_type:
                            structure["instances"] += 1
                        elif "router" in res_type and "interface" not in res_type:
                            structure["routers"] += 1
                
                structures.append(structure)
                
            except Exception as e:
                result["errors"].append(f"Error reading {sub}: {str(e)}")
    
    result["name_duplicates"] = name_duplicates
    
    # Kiểm tra tính nhất quán
    if len(structures) > 1:
        first = structures[0]
        for s in structures[1:]:
            if s != first:
                result["structure_consistent"] = False
                break


def run_scenario2(n_values: List[int], topology_file: Path = None):
    """Chạy kịch bản 2 với các giá trị N"""
    
    # Sử dụng topology mặc định nếu không chỉ định
    if topology_file is None:
        topology_file = SCRIPT_DIR / "topology-scenario2.json"
    
    if not topology_file.exists():
        print(f"Error: Không tìm thấy topology file: {topology_file}")
        sys.exit(1)
    
    # Copy topology vào terraform-generator
    copy_topology_to_generator(topology_file)
    
    # Tạo thư mục kết quả
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = EVALUATION_DIR / "results" / f"scenario2_{timestamp}"
    results_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 80)
    print("KỊCH BẢN 2: ĐÁNH GIÁ KHẢ NĂNG MỞ RỘNG VÀ NHÂN BẢN HẠ TẦNG")
    print("=" * 80)
    print(f"Topology: {topology_file}")
    print(f"Các giá trị N: {n_values}")
    print(f"Kết quả lưu tại: {results_dir}")
    print()
    
    results = {}
    
    for n in n_values:
        log(f"{'='*60}")
        log(f"TEST N = {n}")
        log(f"{'='*60}")
        
        # Cleanup trước mỗi lần test
        log("  Dọn dẹp terraform-projects...")
        cleanup_terraform_projects()
        
        # Chạy generate với N copies
        result = run_generate_with_copies(n)
        results[n] = result
        
        # In kết quả
        log(f"  Kết quả N={n}:")
        log(f"    - Thời gian: {result['total_time']:.2f}s")
        log(f"    - Resources: {result['resources']}")
        log(f"    - Folders: {result['folders_created']}")
        log(f"    - Success: {'✓' if result['success'] else '✗'}")
        log(f"    - Name Dup: {result['name_duplicates']}")
        log(f"    - Consistent: {'✓' if result['structure_consistent'] else '✗'}")
        
        if result["errors"]:
            log(f"    - Errors: {result['errors'][:2]}")
    
    # Lưu kết quả
    results_file = results_dir / "scenario2_results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    # In báo cáo
    print_report(results, n_values)
    
    print(f"\n✓ Kết quả đã lưu: {results_file}")
    
    return results


def print_report(results: Dict, n_values: List[int]):
    """In báo cáo kết quả"""
    print()
    print("=" * 90)
    print("BÁO CÁO KẾT QUẢ KỊCH BẢN 2")
    print("=" * 90)
    
    # Bảng kết quả chính
    print("\n📊 BẢNG KẾT QUẢ:")
    print("-" * 90)
    print(f"{'N':>6} | {'Thời gian (s)':>14} | {'Resources':>10} | {'Folders':>8} | {'Success':>8} | {'Name Dup':>9} | {'Consistent':>10}")
    print("-" * 90)
    
    for n in n_values:
        if n in results:
            r = results[n]
            print(f"{n:>6} | {r['total_time']:>14.2f} | {r['resources']:>10} | {r['folders_created']:>8} | "
                  f"{'✓' if r['success'] else '✗':>8} | {r['name_duplicates']:>9} | "
                  f"{'✓' if r['structure_consistent'] else '✗':>10}")
    
    print("-" * 90)
    
    # Tính tổng và trung bình
    total_time = sum(r['total_time'] for r in results.values())
    total_resources = sum(r['resources'] for r in results.values())
    total_folders = sum(r['folders_created'] for r in results.values())
    success_count = sum(1 for r in results.values() if r['success'])
    total_dup = sum(r['name_duplicates'] for r in results.values())
    all_consistent = all(r['structure_consistent'] for r in results.values())
    
    print()
    print("📈 TỔNG KẾT:")
    print(f"  • Tổng số bản sao: {sum(n_values)}")
    print(f"  • Tổng thời gian: {total_time:.2f}s")
    print(f"  • Tổng resources: {total_resources}")
    print(f"  • Tỷ lệ thành công: {success_count}/{len(n_values)} ({100*success_count/len(n_values):.0f}%)")
    print(f"  • Số trùng tên: {total_dup}")
    print(f"  • Cấu trúc nhất quán: {'✓ Có' if all_consistent else '✗ Không'}")
    
    # So sánh thời gian
    if len(n_values) >= 2:
        print()
        print("📊 PHÂN TÍCH THỜI GIAN:")
        n1 = n_values[0]
        for n in n_values[1:]:
            if n in results and n1 in results:
                t1 = results[n1]['total_time']
                tn = results[n]['total_time']
                # Ước tính thời gian thủ công: t1 * n
                manual_estimate = t1 * n
                speedup = manual_estimate / tn if tn > 0 else 0
                saving = manual_estimate - tn
                print(f"  • N={n}: Framework {tn:.1f}s vs Thủ công (ước) {manual_estimate:.1f}s → Tiết kiệm {saving:.1f}s ({speedup:.1f}x)")


def main():
    """Main function"""
    # Parse arguments
    if len(sys.argv) > 1:
        # Nếu có tham số, parse N values
        try:
            n_values = [int(x.strip()) for x in sys.argv[1].split(",")]
        except ValueError:
            print("Usage: python3 scenario2_scalability.py [N1,N2,N3,...]")
            print("Example: python3 scenario2_scalability.py 1,3,5,10,20,40,60,100")
            sys.exit(1)
    else:
        # Mặc định
        n_values = [1, 3, 5]
    
    # Topology file (optional second argument)
    topology_file = None
    if len(sys.argv) > 2:
        topology_file = Path(sys.argv[2])
    
    # Chạy
    run_scenario2(n_values, topology_file)


if __name__ == "__main__":
    main()
