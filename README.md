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


沒問題！這裡直接幫你把 **FILE\_MAP 與 CRD YAML** 的格式關係、對應方式和實例寫成 Markdown，
你可以直接 copy 存成教材用。
（內容有加上中英雙語說明，註解友善，適合自己或團隊後續查閱！）

---

```markdown
# Kubernetes CRD 與 FILE_MAP 格式對應教學

本教材示範如何設計彈性的 Kubernetes CRD (CustomResourceDefinition) 與 crd-syncer 所需的 `FILE_MAP` 映射格式。適合團隊用於配置多種型別的自定義資源，同步任意 JSON 檔案與 K8s CR。

---

## 1. FILE_MAP 格式說明

**語法：**
```

/路徑/檔名.json=plural\:name\:kind

````

- `/路徑/檔名.json`：本地 JSON 文件路徑
- `plural`：Kubernetes CRD 的複數型名稱（如 services, subscriptions...）
- `name`：該資源的 metadata.name（如 service-info）
- `kind`：CRD 定義的 kind（如 Service、ServiceSpec...）

---

## 2. 彈性 CRD YAML 格式

每個 CRD 建議都用彈性 schema（data 欄位允許任意內容）。

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: <plural>.<group>
spec:
  group: <group>
  versions:
    - name: v1
      served: true
      storage: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              x-kubernetes-preserve-unknown-fields: true  # 彈性內容
  scope: Namespaced
  names:
    plural: <plural>
    singular: <singular>
    kind: <kind>
    shortNames:
      - <縮寫，可省略>
````

**替換尖括號部分為你的參數。**

---

## 3. 實例對應

### (1) CRD YAML 範例

假設你有四種業務物件，分別為 Service、ServiceSpec、Subscription、NodeStatus。

#### a. Service CRD

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: services.ha.example.com
spec:
  group: ha.example.com
  versions:
    - name: v1
      served: true
      storage: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            data:
              type: object
              x-kubernetes-preserve-unknown-fields: true
  scope: Namespaced
  names:
    plural: services
    singular: service
    kind: Service
```

#### b. ServiceSpec CRD

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: servicespecs.ha.example.com
spec:
  group: ha.example.com
  versions:
    - name: v1
      served: true
      storage: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            data:
              type: object
              x-kubernetes-preserve-unknown-fields: true
  scope: Namespaced
  names:
    plural: servicespecs
    singular: servicespec
    kind: ServiceSpec
```

#### c. Subscription CRD

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: subscriptions.ha.example.com
spec:
  group: ha.example.com
  versions:
    - name: v1
      served: true
      storage: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            data:
              type: object
              x-kubernetes-preserve-unknown-fields: true
  scope: Namespaced
  names:
    plural: subscriptions
    singular: subscription
    kind: Subscription
```

#### d. NodeStatus CRD

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: nodestatuses.ha.example.com
spec:
  group: ha.example.com
  versions:
    - name: v1
      served: true
      storage: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            data:
              type: object
              x-kubernetes-preserve-unknown-fields: true
  scope: Namespaced
  names:
    plural: nodestatuses
    singular: nodestatus
    kind: NodeStatus
```

---

### (2) FILE\_MAP 配置實例

搭配上述 CRD，FILE\_MAP 寫法如下：

```
/app/information/service.json=services:service-info:Service
/app/information/serviceSpec.json=servicespecs:servicespec-info:ServiceSpec
/app/information/subscription.json=subscriptions:subscription-info:Subscription
/app/information/nodestatus.json=nodestatuses:nodestatus-info:NodeStatus
```

---

### (3) JSON 檔案內容自由

`service.json` 舉例內容如下（`data` 欄位會存到 CR）：

```json
{
  "foo": "bar",
  "list": [1,2,3],
  "enable": true,
  "settings": {
    "timeout": 10
  }
}
```

syncer 會把這些內容包在 CR 的 `data` 欄位中，如下：

```yaml
apiVersion: ha.example.com/v1
kind: Service
metadata:
  name: service-info
  namespace: arha-system
data:
  foo: bar
  list: [1,2,3]
  enable: true
  settings:
    timeout: 10
```

---

## 4. 加新類型也很簡單

只要：

1. 複製 CRD yaml，改 plural/name/kind
2. 在 FILE\_MAP 新增對應一行

例如：

```
/app/information/another.json=anothercrds:another-info:AnotherKind
```

並新增一份對應的 CRD 定義。

---

## 5. 教材小結

* FILE\_MAP 與 CRD YAML 以 plural/name/kind 對應
* CRD 設計推薦彈性（data 可任意 key/value）
* 配置易於維護與擴展，適用 syncer/ops/多業務
* 新需求只需補一行 FILE\_MAP 與一份 CRD yaml

---

> 💡 **建議所有團隊新專案均採此彈性設計，可配合 GitOps 持續迭代！**

```

如需附圖/流程圖/英文版、或直接一份完整 md 檔案，歡迎再指定！
```
