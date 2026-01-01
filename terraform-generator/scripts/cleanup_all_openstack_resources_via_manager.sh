#!/bin/bash
# cleanup_all_openstack_resources_via_manager.sh
# Xoá toàn bộ tài nguyên OpenStack sử dụng openstack_config_manager.py (profile active)
# Sử dụng: ./cleanup_all_openstack_resources_via_manager.sh

set -e
PYTHON="python3"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANAGER="$SCRIPT_DIR/../openstack_config_manager.py"

run() {
  $PYTHON "$MANAGER" openstack "$@"
}

echo "[!] Đang xoá toàn bộ instance..."
for id in $(run server list -f value -c ID); do
  run server delete "$id"
  sleep 0.2
done


# Lặp lại tháo subnet khỏi router và xoá port router_interface cho đến khi sạch
while true; do
  echo "[!] Đang tháo toàn bộ subnet khỏi router..."
  removed_any=false
  for router in $(run router list -f value -c ID); do
      for subnet in $(run router show $router -f json | jq -r '.interfaces_info[].subnet_id'); do
          run router remove subnet $router $subnet && removed_any=true
      done
  done
  # Thử xoá port, nếu không còn port router_interface thì break
  echo "[!] Đang xoá toàn bộ port..."
  failed=0
  for id in $(run port list -f value -c ID); do
    # Kiểm tra device_owner
    owner=$(run port show $id -f json | jq -r '.device_owner')
    if [[ "$owner" == "network:router_interface" ]]; then
      continue
    fi
    run port delete "$id" || failed=1
    sleep 0.1
  done
  # Nếu không còn port router_interface nào thì break
  count=$(run port list -f json | jq '[.[] | select(.device_owner=="network:router_interface")] | length')
  if [[ "$count" == "0" ]]; then
    break
  fi
done

echo "[!] Đang xoá toàn bộ router interface..."
for router in $(run router list -f value -c ID); do
    for subnet in $(run router show $router -f json | jq -r '.interfaces_info[].subnet_id'); do
        run router remove subnet $router $subnet || true
    done
done

echo "[!] Đang xoá toàn bộ router..."
for id in $(run router list -f value -c ID); do
  run router delete "$id"
  sleep 0.1
done

echo "[!] Đang xoá toàn bộ subnet..."
for id in $(run subnet list -f value -c ID); do
  run subnet delete "$id" 2>&1 || echo "[!] Bỏ qua subnet $id (không đủ quyền hoặc subnet đặc biệt)"
  sleep 0.1
done

echo "[!] Đang xoá toàn bộ network..."
for id in $(run network list -f value -c ID); do
  run network delete "$id" 2>&1 || echo "[!] Bỏ qua network $id (không đủ quyền hoặc network đặc biệt)"
  sleep 0.1
done

echo "[✓] Đã xoá xong toàn bộ tài nguyên OpenStack (qua openstack_config_manager.py)."