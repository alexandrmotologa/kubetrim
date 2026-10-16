# KubeTrim CLI Reference

Complete command reference for the `kubetrim` utility.

## Global Options

```text
Usage: kubetrim [OPTIONS] COMMAND [ARGS]...

Options:
  --kubeconfig PATH      Path to kubeconfig file [default: ~/.kube/config]
  --context TEXT         Kubernetes context name from ~/.kube/config
  --help                 Show this message and exit
```

---

## Commands

### `scan`

Analyzes Kubernetes workloads across namespaces and displays a detailed financial rightsizing report.

```bash
kubetrim scan [OPTIONS]
```

**Options:**
- `--namespace, -n TEXT`: Target namespace (defaults to all non-system namespaces).
- `--context TEXT`: Specific cluster context name from kubeconfig.
- `--provider, -p [aws|gcp|azure|baremetal]`: Cloud provider pricing model [default: `aws`].
- `--profile TEXT`: Rightsizing profile name (`conservative`, `balanced`, `aggressive`) [default: `balanced`].
- `--prometheus-url TEXT`: URL to Prometheus server for historical metrics.
- `--window TEXT`: Historical evaluation window (e.g., `7d`, `14d`, `30d`) [default: `14d`].
- `--min-savings FLOAT`: Minimum monthly dollar savings threshold to include a workload.
- `--output, -o [table|json|csv|html]`: Output format [default: `table`].
- `--export-file PATH`: Optional path to write report output.

---

### `binpack`

Simulates Karpenter and Kubernetes Cluster Autoscaler multi-dimensional node bin-packing to compute physical worker node consolidation, removable node counts, and net cloud bill savings.

```bash
kubetrim binpack [OPTIONS]
```

**Options:**
- `--provider, -p [aws|gcp|azure|baremetal]`: Cloud provider pricing rate card [default: `aws`].
- `--profile TEXT`: Rightsizing profile [default: `balanced`].
- `--instance-type TEXT`: Default worker node instance type [default: `m6i.xlarge`].
- `--namespace, -n TEXT`: Namespace filter.

---

### `gate`

Enforces FinOps budget guardrails in CI/CD pipelines. Evaluates workloads in local manifests or live clusters and exits with code 1 if detected waste breaches configured thresholds.

```bash
kubetrim gate [OPTIONS]
```

**Options:**
- `--manifest, -m PATH`: Path to local Kubernetes manifest file or directory to evaluate.
- `--max-waste-usd FLOAT`: Maximum allowed monthly recoverable waste in dollars [default: `100.0`].
- `--max-waste-pct FLOAT`: Maximum allowed waste percentage [default: `35.0`].
- `--fail-on-waste / --no-fail-on-waste`: Return non-zero exit code 1 on budget breach [default: `--no-fail-on-waste`].
- `--pr-comment-file PATH`: Output path for formatted GitHub PR Markdown summary table.
- `--provider, -p TEXT`: Cloud provider pricing rate card [default: `aws`].
- `--profile TEXT`: Rightsizing profile [default: `balanced`].

---

### `gitops-export`

Creates a dedicated Git branch and commits rightsized Kubernetes manifests or Helm `values.yaml` patches ready for automated Pull Request creation.

```bash
kubetrim gitops-export [OPTIONS] PATH
```

**Options:**
- `PATH`: Path to Kubernetes YAML manifest file or Helm `values.yaml`.
- `--branch, -b TEXT`: Name of Git branch to create (defaults to `finops/rightsize-<workload>-<timestamp>`).
- `--dry-run`: Preview patch diff without writing files or creating Git commits.
- `--provider, -p TEXT`: Cloud provider pricing rate card [default: `aws`].
- `--profile TEXT`: Rightsizing profile [default: `balanced`].

---

### `contexts`

Discovers and lists all available Kubernetes cluster contexts configured in `~/.kube/config`.

```bash
kubetrim contexts
```

---

### `diff`

Generates unified diff patches or Kustomize overlays for local Kubernetes manifests against live cluster recommendations or metrics files.

```bash
kubetrim diff [OPTIONS] PATH
```

**Options:**
- `--profile TEXT`: Rightsizing profile [default: `balanced`].
- `--provider TEXT`: Cloud provider for cost metrics [default: `aws`].
- `--output, -o PATH`: Output file path for generated unified diff.
- `--kustomize`: Generate Kustomize strategic merge patch syntax instead of unified diff.

---

### `patch`

Applies rightsizing adjustments directly to local Helm `values.yaml` or Kubernetes manifests.

```bash
kubetrim patch [OPTIONS] PATH
```

**Options:**
- `--profile TEXT`: Rightsizing profile to apply.
- `--dry-run / --no-dry-run`: Preview changes without modifying files [default: `--dry-run`].
- `--write, -w`: Write changes directly to target manifest or `values.yaml`.
- `--backup`: Create `.bak` backup file before modifying in-place.

---

### `tui`

Launches the interactive terminal user interface powered by Textual, featuring live node bin-packing KPIs, HPA conflict guards, and Spot indicators.

```bash
kubetrim tui [OPTIONS]
```

**Options:**
- `--namespace, -n TEXT`: Initial namespace filter.
- `--provider TEXT`: Cloud pricing provider.
- `--profile TEXT`: Initial rightsizing profile.

---

### `web`

Starts the browser-based FinOps Web Studio powered by FastAPI, featuring interactive What-If headroom sliders and Karpenter bin-packing density explorer.

```bash
kubetrim web [OPTIONS]
```

**Options:**
- `--host TEXT`: Bind host [default: `127.0.0.1`].
- `--port, -p INTEGER`: Bind port [default: `8980`].
- `--open-browser / --no-open`: Automatically open default web browser.

---

### `pricing`

Inspects, compares, and exports cloud provider pricing rate cards.

```bash
kubetrim pricing [OPTIONS]
```

**Options:**
- `--provider [aws|gcp|azure|baremetal|all]`: Provider to inspect [default: `all`].
