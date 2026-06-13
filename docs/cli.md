# CLI Reference

The `cah` CLI provides commands for running agents, inspecting results, and
managing the harness.

## Global Options

| Option | Description |
|--------|-------------|
| `--version` | Print version and exit |
| `--verbose`, `-v` | Enable verbose output |
| `--log-level` | Override log level (DEBUG, INFO, WARNING, ERROR) |

## Run Commands

### `cah run`

Execute a run against a target repository.

```bash
cah run [OPTIONS] GOAL
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `GOAL` | Path to `goal.yaml` or `manifest.yaml` |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--repo`, `-r` | `.` | Path to target repository |
| `--agent`, `-a` | `scripted` | Agent type: `scripted`, `google-adk`, `replay` |
| `--model`, `-m` | — | Model override |
| `--mode` | `constrained-verification` | Experiment mode |

### `cah resume`

Resume an interrupted run.

```bash
cah resume RUN_ID
```

### `cah cancel`

Cancel a running or paused run.

```bash
cah cancel RUN_ID
```

### `cah status`

Print a one-line status summary for a run.

```bash
cah status RUN_ID
```

**Example output:**
```
Run a1b2c3d4 | iterations=3 duration=12.4s approval=approved
decisions=[ACCEPT:2, COMPLETE:1] eval=(3P/0F) artifacts=5 tokens=4200
```

## Report Commands

### `cah report run`

Generate a detailed run report.

```bash
cah report run [OPTIONS] RUN_ID
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--format` | `markdown` | Output format: `markdown` or `json` |

### `cah report compare`

Compare two runs side-by-side.

```bash
cah report compare RUN_ID_A RUN_ID_B
```

Displays a table with status, iterations, duration, model calls, tokens,
evaluator pass/fail, approval status, artifact count, and decisions.

### `cah report experiment`

List all runs matching an experiment mode.

```bash
cah report experiment EXPERIMENT_MODE
```

Displays a table of runs with their key metrics.

## Artifact Commands

### `cah artifacts verify`

Verify the artifact hash chain for a run.

```bash
cah artifacts verify RUN_ID
```

## Experiment Commands

### `cah experiment run`

Run a benchmark experiment multiple times.

```bash
cah experiment run [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--repetitions` | `1` | Number of repetitions |
| `--benchmark` | `payment_webhook` | Benchmark name |

## Inspect Commands

### `cah inspect`

Inspect run details, events, candidates, and artifacts.

```bash
cah inspect run RUN_ID
cah inspect events RUN_ID
cah inspect candidates RUN_ID
cah inspect artifacts RUN_ID
```

## Database Commands

### `cah db upgrade`

Run database schema migrations.

```bash
cah db upgrade
```

## Doctor Command

### `cah doctor`

Check system health and configuration.

```bash
cah doctor
```

## Init Command

### `cah init`

Initialize a CAH runtime directory.

```bash
cah init [--path .]
```
