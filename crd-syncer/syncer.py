#!/usr/bin/env python3
"""
crd-syncer: A lightweight JSON file ↔ Kubernetes CustomResource synchronizer.

This script watches one or more JSON files on the local filesystem and keeps the
contents in sync with corresponding Kubernetes CustomResources (CRs).  It also
observes the CRs and writes any changes back to the files.  By default the
synchroniser runs in‑cluster (loading a ServiceAccount token) but can fall
back to using the local kubeconfig for development.

Configuration is provided via environment variables:

    FILE_MAP        Required.  A newline-separated list of mappings in the form
                    `/path/to/file.json=plural:name`.  The plural refers to the
                    CRD plural name (e.g. “services”), and `name` is the name of
                    the CR instance to update (e.g. “service-info”).  Each file
                    may map to a different CR.

    CRD_GROUP       The API group for your CRDs (default: "ha.example.com").

    CRD_VERSION     The version of your CRD (default: "v1").

    CRD_NAMESPACE   The namespace containing the CR instances (default: "default").

    IN_CLUSTER      Set to "true" if running inside a Kubernetes cluster.
                    When false, the script will load your local kubeconfig.

    SYNC_INTERVAL   Polling interval in seconds (default: "5").

The synchroniser uses a simple hashing mechanism (MD5 of JSON dumps) to detect
changes on both the file side and the CR side.  Only when a change is detected
and it differs from the previously applied state will a sync occur.
"""

import os
import time
import json
import hashlib
from typing import Dict, Tuple

from kubernetes import client, config
from kubernetes.client.rest import ApiException


def load_k8s_config(in_cluster: bool) -> None:
    """
    Load Kubernetes configuration.  If running in cluster, use the
    ServiceAccount token; otherwise, fall back to the user's kubeconfig.
    """
    if in_cluster:
        config.load_incluster_config()
    else:
        config.load_kube_config()


def get_custom_objects_api(in_cluster: bool) -> client.CustomObjectsApi:
    """
    Return an initialised CustomObjectsApi.
    """
    load_k8s_config(in_cluster)
    return client.CustomObjectsApi()


def read_custom_resource(
    api: client.CustomObjectsApi,
    group: str,
    version: str,
    namespace: str,
    plural: str,
    name: str,
) -> Dict:
    """
    Read a namespaced custom resource and return its "data" field.

    If the resource does not exist (404), return an empty dict.
    Raise other exceptions for unexpected failures.
    """
    try:
        obj = api.get_namespaced_custom_object(group, version, namespace, plural, name)
        return obj.get("data", {}) or {}
    except ApiException as e:
        if e.status == 404:
            return {}
        raise


def write_custom_resource(
    api: client.CustomObjectsApi,
    group: str,
    version: str,
    namespace: str,
    plural: str,
    name: str,
    data: Dict,
) -> None:
    """
    Create or replace a namespaced custom resource with the provided data.
    """
    body = {
        "apiVersion": f"{group}/{version}",
        "kind": "Data",
        "metadata": {"name": name},
        "data": data,
    }
    try:
        api.replace_namespaced_custom_object(
            group, version, namespace, plural, name, body
        )
    except ApiException as e:
        if e.status == 404:
            api.create_namespaced_custom_object(
                group, version, namespace, plural, body
            )
        else:
            raise


def file_hash(obj: Dict) -> str:
    """
    Return a stable MD5 hash of a Python object representing JSON data.
    The object is dumped with sorted keys to ensure consistent hashing.
    """
    return hashlib.md5(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def read_json_file(path: str) -> Dict:
    """
    Read a JSON file from disk.  If the file does not exist or is empty, return {}.
    """
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        # If file cannot be parsed as JSON, treat as empty to avoid crashes.
        return {}


def write_json_file(path: str, data: Dict) -> None:
    """
    Write a Python dict to a JSON file with pretty formatting.
    Create intermediate directories if needed.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def parse_file_map(map_string: str) -> Dict[str, Tuple[str, str]]:
    """
    Parse the FILE_MAP string into a dictionary of file path to (plural, name).

    Each line in map_string should have the format:
        /path/to/file.json=plural:name
    """
    mappings = {}
    for line in map_string.strip().splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        file_path, cr_spec = line.split("=", 1)
        plural, name = cr_spec.split(":", 1)
        mappings[file_path.strip()] = (plural.strip(), name.strip())
    return mappings


def main() -> None:
    """
    Main loop: repeatedly synchronise local files and CRDs based on configuration.
    """
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
    # Track last applied hashes for files and CRs to avoid infinite update loops.
    last_file_hashes = {path: "" for path in file_map}
    last_cr_hashes = {path: "" for path in file_map}

    print("Starting crd-syncer")
    print(f"Watching {len(file_map)} file(s) with polling interval {sync_interval}s")
    while True:
        # Acquire API inside loop to renew stale credentials if needed.
        api = get_custom_objects_api(in_cluster)
        for file_path, (plural, name) in file_map.items():
            # Read current data from file and CR
            file_data = read_json_file(file_path)
            cr_data = read_custom_resource(api, group, version, namespace, plural, name)
            # Compute current hashes
            current_file_hash = file_hash(file_data)
            current_cr_hash = file_hash(cr_data)
            # Determine if file → CR update is needed
            if current_file_hash != last_file_hashes[file_path] and current_file_hash != current_cr_hash:
                print(f"[File → CR] Updating {plural}/{name} from {file_path}")
                write_custom_resource(api, group, version, namespace, plural, name, file_data)
                last_file_hashes[file_path] = current_file_hash
                last_cr_hashes[file_path] = current_file_hash
            # Determine if CR → file update is needed
            elif current_cr_hash != last_cr_hashes[file_path] and current_cr_hash != current_file_hash:
                print(f"[CR → File] Updating {file_path} from {plural}/{name}")
                write_json_file(file_path, cr_data)
                last_file_hashes[file_path] = current_cr_hash
                last_cr_hashes[file_path] = current_cr_hash
        time.sleep(sync_interval)


if __name__ == "__main__":
    main()