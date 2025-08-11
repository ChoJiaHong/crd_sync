#!/usr/bin/env python3
"""
crd-syncer: A lightweight JSON file ↔ Kubernetes CustomResource synchronizer.
"""

import os
import time
import json
import hashlib
from typing import Dict, Tuple

from kubernetes import client, config
from kubernetes.client.rest import ApiException

# ---- Guard switches (env) ----------------------------------------------------
# CR 或 CRD 不存在時，保護本地檔：不做 CR→File
PROTECT_LOCAL_ON_CR_ABSENT = os.getenv("PROTECT_LOCAL_ON_CR_ABSENT", "true").lower() == "true"
# 當 CR 的 payload 是空 {} 時，是否跳過 CR→File
SKIP_EMPTY_CR_TO_FILE = os.getenv("SKIP_EMPTY_CR_TO_FILE", "true").lower() == "true"


def load_k8s_config(in_cluster: bool) -> None:
    if in_cluster:
        config.load_incluster_config()
    else:
        config.load_kube_config()


def get_custom_objects_api(in_cluster: bool) -> client.CustomObjectsApi:
    load_k8s_config(in_cluster)
    return client.CustomObjectsApi()


def read_custom_resource(
    api: client.CustomObjectsApi,
    group: str,
    version: str,
    namespace: str,
    plural: str,
    name: str,
) -> Tuple[Dict, bool]:
    """
    回傳 (payload, exists)
    - exists=False 表示 404（該 CR 不存在，或 CRD 被刪）
    - exists=True 表示讀到物件（即使內容為 {}）
    內容讀取自 spec。
    """
    try:
        obj = api.get_namespaced_custom_object(group, version, namespace, plural, name)
        val = obj.get("spec", {})
        if isinstance(val, dict):
            return val, True
        return ({"raw": val} if val is not None else {}), True
    except ApiException as e:
        if e.status == 404:
            return {}, False
        raise


def write_custom_resource(
    api: client.CustomObjectsApi,
    group: str,
    version: str,
    namespace: str,
    plural: str,
    name: str,
    kind: str,
    data: Dict,
) -> None:
    """
    僅寫入 spec，並帶上 resourceVersion 以避免 422。
    """
    body = {
        "apiVersion": f"{group}/{version}",
        "kind": kind,
        "metadata": {"name": name},
        "spec": data,
    }
    try:
        current = api.get_namespaced_custom_object(group, version, namespace, plural, name)
        rv = current.get("metadata", {}).get("resourceVersion")
        if rv:
            body["metadata"]["resourceVersion"] = rv
        api.patch_namespaced_custom_object(group, version, namespace, plural, name, body)
    except ApiException as e:
        if e.status == 404:
            # 物件不存在就建立（若 CRD 被刪將仍 404；交由上層觀察 log）
            api.create_namespaced_custom_object(group, version, namespace, plural, body)
        else:
            raise


def file_hash(obj: Dict) -> str:
    return hashlib.md5(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def read_json_file(path: str) -> Dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            content = json.load(f)
            if isinstance(content, dict):
                return content
            return {"raw": content}
    except Exception:
        return {}


def write_json_file(path: str, data: Dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    output = data
    if isinstance(data, dict) and list(data.keys()) == ["raw"]:
        output = data["raw"]
    with open(path, "w") as f:
        json.dump(output, f, indent=2)


def parse_file_map(map_string: str) -> Dict[str, Tuple[str, str, str]]:
    """
    解析成: file_path -> (plural, name, kind)
    例: /path/file.json=services:service-info:Service
    """
    mappings = {}
    for line in map_string.strip().splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        file_path, cr_spec = line.split("=", 1)
        parts = cr_spec.split(":")
        plural, name = parts[:2]
        kind = parts[2] if len(parts) > 2 else "Service"
        mappings[file_path.strip()] = (plural.strip(), name.strip(), kind.strip())
    return mappings


def main() -> None:
    file_map_str = os.environ.get("FILE_MAP")
    if not file_map_str:
        raise SystemExit("Environment variable FILE_MAP is required")

    group = os.environ.get("CRD_GROUP", "ha.example.com")
    version = os.environ.get("CRD_VERSION", "v1")
    namespace = os.environ.get("CRD_NAMESPACE", os.environ.get("NAMESPACE", "default"))
    in_cluster = os.environ.get("IN_CLUSTER", "true").lower() == "true"
    try:
        sync_interval = float(os.environ.get("SYNC_INTERVAL", "5"))
    except ValueError:
        sync_interval = 5.0

    file_map = parse_file_map(file_map_str)
    last_file_hashes = {path: "" for path in file_map}
    last_cr_hashes = {path: "" for path in file_map}

    print("Starting crd-syncer")
    print(f"Watching {len(file_map)} file(s) with polling interval {sync_interval}s")
    while True:
        api = get_custom_objects_api(in_cluster)
        for file_path, (plural, name, kind) in file_map.items():
            # 讀本地
            file_data = read_json_file(file_path)
            current_file_hash = file_hash(file_data)

            # 讀 CR（spec），並知道是否存在
            cr_data, cr_exists = read_custom_resource(api, group, version, namespace, plural, name)
            current_cr_hash = file_hash(cr_data) if cr_exists else last_cr_hashes[file_path]

            # File → CR：本地有變、且不同於 CR
            if current_file_hash != last_file_hashes[file_path] and current_file_hash != current_cr_hash:
                print(f"[File → CR] Updating {plural}/{name} from {file_path}")
                try:
                    write_custom_resource(api, group, version, namespace, plural, name, kind, file_data)
                    last_file_hashes[file_path] = current_file_hash
                    last_cr_hashes[file_path] = current_file_hash
                except ApiException as e:
                    print(f"[Error] Write CR failed for {plural}/{name}: {e}")

            # CR → File：只有在 CR 存在時才考慮；且可選擇跳過空 payload
            elif cr_exists and current_cr_hash != last_cr_hashes[file_path] and current_cr_hash != current_file_hash:
                if SKIP_EMPTY_CR_TO_FILE and cr_data == {}:
                    print(f"[CR → File] Skip empty spec for {plural}/{name} (protect local).")
                    # 不更新 last_*，避免下一輪仍判定差異；但這也表示只要 CR 還是 {}，每輪都會跳過
                    last_cr_hashes[file_path] = current_cr_hash
                else:
                    print(f"[CR → File] Updating {file_path} from {plural}/{name}")
                    write_json_file(file_path, cr_data)
                    last_file_hashes[file_path] = current_cr_hash
                    last_cr_hashes[file_path] = current_cr_hash

            # CR 不存在（404 / CRD 可能被刪）
            elif not cr_exists:
                if PROTECT_LOCAL_ON_CR_ABSENT:
                    print(f"[Guard] {plural}/{name} not found. Protect local file: {file_path}.")
                # 不更新 last_cr_hashes，保留現況；允許 File→CR 在未來某次變動時重建該 CR

        time.sleep(sync_interval)


if __name__ == "__main__":
    main()
