# crd-syncer

`crd-syncer` is a lightweight utility for keeping JSON files and Kubernetes
CustomResources in sync.  It allows an existing application to persist
its state as JSON files without any awareness of Kubernetes.  A separate
synchroniser watches the files, updates the corresponding CustomResource
instances, and writes changes from the cluster back to the files.

## Features

- 🔁 **Two-way synchronisation** between JSON files and CustomResource (CR) instances.
- 📁 **No code changes required** for your existing application; it keeps writing JSON.
- ⚙️ **Configurable** via environment variables: map any file to any CR.
- 🐳 **Container-ready**: run as a standalone Pod or sidecar alongside your app.
- 🛠 **Simple implementation**: polling with MD5 hash prevents update loops.

## Quick Start

### Build and run locally

```bash
git clone https://github.com/yourname/crd-syncer.git
cd crd-syncer
docker build -t crd-syncer:latest .

# Run locally using your kubeconfig:
export FILE_MAP="/path/to/service.json=services:service-info"
export CRD_GROUP=ha.example.com
export CRD_VERSION=v1
export CRD_NAMESPACE=default
export IN_CLUSTER=false
docker run --rm -v /path/to:/path/to crd-syncer:latest
```

### Deploy to Kubernetes

1. **Install your CRDs** for the plural names you intend to use (e.g. `services.ha.example.com`).
2. **Provision a `PersistentVolumeClaim`** named `arha-system-information` in your namespace.  This PVC should be mounted
   read/write by the syncer and any other Pods that write the JSON files.
3. **Apply the provided `deployment.yaml`**:

```bash
kubectl apply -f deployment.yaml
```

This deployment uses a single `crd-syncer` container that mounts `/app/information` from the PVC and syncs four
JSON files (`service.json`, `serviceSpec.json`, `subscription.json`, `nodestatus.json`) into four CRs.

## Configuration

The synchroniser is configured entirely via environment variables:

| Variable        | Default              | Description |
|-----------------|----------------------|-------------|
| `FILE_MAP`      | *(required)*         | Mapping of file paths to CR identifiers.  Each line has the form `/path/to/file.json=plural:name`. |
| `CRD_GROUP`     | `ha.example.com`     | API group for the CRDs. |
| `CRD_VERSION`   | `v1`                 | Version of the CRDs. |
| `CRD_NAMESPACE` | `default`            | Namespace of the CR instances. |
| `IN_CLUSTER`    | `true`               | Load in-cluster configuration when true; fallback to kubeconfig when false. |
| `SYNC_INTERVAL` | `5`                  | Polling interval in seconds. |

Multiple mappings can be specified by separating lines with newline characters (`\n`).  For example:

```
FILE_MAP="/app/information/service.json=services:service-info\n/app/information/nodestatus.json=nodestatuses:nodestatus-info"
```

## Building your own image

To build your own Docker image:

```bash
docker build -t myrepo/crd-syncer:1.0 .
docker push myrepo/crd-syncer:1.0
```

You can then update the image reference in `deployment.yaml` to match your repository.

## License

This project is licensed under the MIT License.  See [LICENSE](LICENSE) for details.
