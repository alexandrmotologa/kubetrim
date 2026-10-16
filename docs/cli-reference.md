# KubeTrim CLI Reference

Complete command reference for the `kubetrim` utility.

## Global Options

```text
Usage: kubetrim [OPTIONS] COMMAND [ARGS]...

Options:
  --kubeconfig PATH      Path to kubeconfig file [default: ~/.kube/config]
  --context TEXT         Kubernetes context name
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
- `--provider, -p [aws|gcp|azure|baremetal]`: Cloud provider pricing model [default: `aws`].
- `--profile TEXT`: Rightsizing profile name (`conservative`, `balanced`, `aggressive`) [default: `balanced`].
- `--prometheus-url TEXT`: URL to Prometheus server for historical metrics.
- `--window TEXT`: Historical evaluation window (e.g., `7d`, `14d`, `30d`) [default: `14d`].
- `--min-savings FLOAT`: Minimum monthly dollar savings threshold to include a workload.
- `--output, -o [table|json|csv|html]`: Output format [default: `table`].
- `--export-file PATH`: Optional path to write report output.

---

### `diff`

Generates unified diff patches for local Kubernetes manifests or Helm charts against live cluster recommendations or metrics files.

```bash
kubetrim diff [OPTIONS] PATH
```

**Options:**
- `--profile TEXT`: Rightsizing profile [default: `balanced`].
- `--provider TEXT`: Cloud provider for cost metrics [default: `aws`].
- `--output, -o PATH`: Output file path for generated unified diff.
- `--kustomize`: Generate Kustomize patch syntax instead of standard unified diff.

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

Launches the interactive terminal user interface powered by Textual.

```bash
kubetrim tui [OPTIONS]
```

**Options:**
- `--namespace, -n TEXT`: Initial namespace filter.
- `--provider TEXT`: Cloud pricing provider.
- `--profile TEXT`: Initial rightsizing profile.

---

### `web`

Starts the browser-based FinOps Web Studio powered by FastAPI.

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
