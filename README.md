# Neuri

> **Vendor-Agnostic, Multi-Agent Neuroscience Meta-Harness**

Neuri is an autonomous neuroscience research harness designed to orchestrate complex multi-agent pipelines across public neuroscience ecosystems (BIDS, FSL, FreeSurfer, ANTs, Nilearn, MRtrix3, DIPY, MNE-Python, PyMC, and `sbi`) and vendor-diverse LLM CLI drivers (Google Antigravity `agy`, OpenAI Codex CLI `codex`, OpenCode, OpenClaw, and local Ollama).

Built around an **interactive chat-first terminal interface** (like `agy` or `claude`), Neuri features a strictly decoupled, UI-agnostic session engine ready to migrate smoothly into a full Desktop (Tauri/Electron) or Web GUI.

---

## Key Features

- 💬 **Interactive Terminal Chat Interface:** Typing `neuri` immediately launches an interactive Textual chat center with markdown rendering, collapsible sub-agent `<thinking>` reasoning drawers, and live telemetry status bars.
- ⚡ **Interactive Slash Commands:** Run `/init`, `/skills`, `/status`, `/harness`, `/retry`, `/cancel`, `/clear`, and `/help` directly inside the chat prompt with tab auto-completion.
- 🔄 **UI-Agnostic Session Engine (`NeuriSessionEngine`):** Core orchestration logic communicates purely via typed async events (`SessionEvent`), ensuring any future Desktop/Web GUI can attach with zero changes to orchestration.
- 🔒 **Deterministic Zero-Token Pre-Flight Gate:** Strictly verifies Protected Health Information (PHI) sanitization (`phi_sanitized == True`), coordinate space alignment (e.g. MNI152 vs. native space), and artifact file existence before any LLM context is loaded or subprocess is spawned.
- 🗄️ **SQLite WAL Blackboard State Engine:** Checkpoints all workflows, task nodes, DAG edges, remote artifacts, telemetry events, and citation ledgers with topological dependency traversal and atomic cycle detection.
- 🛡️ **Streaming TelemetryTap & Circuit Breakers:** Real-time stream parsing for `<thinking>` traces and multi-vendor NDJSON, backed by hard token ceilings, USD cost limits, and consecutive tool failure circuit breakers.
- 🔌 **Vendor-Agnostic Harness Adapters:** Plug-and-play drivers for Tier-1 harnesses (Antigravity `agy`, OpenAI Codex CLI `codex`) and Tier-2 harnesses (OpenCode, OpenClaw, and local zero-cost Ollama).

---

## Installation

Neuri requires **Python 3.12+** and is managed using [`uv`](https://github.com/astral-sh/uv).

### Quick Install (Recommended)

Run the automated installer script from the repository root:

```bash
git clone https://github.com/your-org/neuri.git
cd neuri
./install.sh
```

Or using `make`:

```bash
make install
```

This single command will:
1. Verify or install `uv` automatically.
2. Synchronize project dependencies in the workspace.
3. Install the executable `neuri` into `~/.local/bin` using `uv tool install --editable . --force`.
4. Bootstrap and copy all base templates and assets (`global/`, `skills/`, `mcp/`, `rules/`, `themes/`) from `./neuri` into `$HOME/.neuri`.
5. Ensure `~/.local/bin` is in your shell `PATH` so typing `neuri` anywhere immediately launches Neuri.

### Manual Installation

Alternatively, install manually using `uv`:

```bash
# 1. Sync dependencies
uv sync --all-extras

# 2. Install editable CLI tool to ~/.local/bin
uv tool install --editable . --force

# 3. Bootstrap base assets into ~/.neuri
neuri install
```

### Verify Installation
```bash
# Check version
neuri --version

# Run the full test suite
uv run pytest -v
```

---

## How to Use Neuri

Neuri supports two primary interaction modes:
1. **Interactive Terminal Chat Center** (Default: launched via bare `neuri`)
2. **Headless Scripting & Pipeline Execution** (Invoked via `neuri -p "<prompt>"`)

---

### Mode 1: Interactive Terminal Chat Center

Simply type `neuri` to launch the interactive chat window:

```bash
uv run neuri
```

#### What You Will See in the Interface:
1. **Header & Workspace Banner:** Displays the active working directory, whether `.neuri/` has been initialized (`[Initialized]` vs. `[Type /init to setup]`), and the default harness.
2. **Scrollable Chat Canvas:** Renders user turns, structured assistant responses in GitHub-flavored markdown, and collapsible `🧠 Reasoning Trace` drawers containing raw thinking steps from sub-agents.
3. **Prompt Input Box:** An interactive input area (`> Type a research prompt or /command...`) supporting both natural language instructions and slash commands.
4. **Live Telemetry Footer:** Real-time status bar showing active harness backend, token consumption tally, and estimated cumulative USD cost.

---

### Interactive Slash Commands

Type any of the following commands into the chat prompt:

| Slash Command | Arguments | Description | Example |
| :--- | :--- | :--- | :--- |
| `/init` | — | Initialize the current directory as a Neuri workspace (`.neuri/` configuration, SQLite Blackboard, provenance log, and BibTeX ledger). | `/init` |
| `/skills` | `[list \| <id>]` | List all available neuroscience skills or inspect inputs, triggers, and modalities for a specific skill. | `/skills`<br>`/skills bids-standard` |
| `/status` | — | View workspace directory, remote host, blackboard node counts, and token/cost telemetry. | `/status` |
| `/harness` | `[<role> <harness_id>]` | Inspect current role-to-harness mappings or dynamically update which harness backs a sub-agent role. | `/harness`<br>`/harness neuroimaging_specialist codex` |
| `/retry` | `<node_id>` | Manually reset and retry a DAG node paused in `WAITING_OPERATOR` state. | `/retry node_wf1_2_bet` |
| `/cancel` | `<node_id>` | Cancel a DAG node paused in `WAITING_OPERATOR` state. | `/cancel node_wf1_2_bet` |
| `/clear` | — | Clear the visible chat transcript while preserving persistent SQLite Blackboard state. | `/clear` |
| `/help` | — | Display a quick-reference card of all available commands and keyboard shortcuts. | `/help` |
| `/exit` | — | Cleanly terminate the interactive session (or press `Ctrl+C` / `Ctrl+Q`). | `/exit` |

---

### Natural Language Research Prompts

Inside the interactive chat window, type research instructions in plain English. Neuri decomposes your instruction into a Directed Acyclic Graph (DAG) of specialized sub-agent tasks using the Tier-0 skills index:

```text
> Validate BIDS dataset in /data/bids/sub-01 and perform brain extraction on the T1w volume using BET.
```

1. **Planning:** Neuri matches triggers in your prompt against the skills catalog and registers DAG nodes in SQLite `state.db`.
2. **Pre-Flight Validation:** Neuri enforces zero-token checks (PHI sanitization, coordinate space consistency, local file existence).
3. **Subprocess Dispatch:** The node is dispatched to the configured harness (e.g. `agy` or `codex`).
4. **Live Telemetry:** Streaming `<thinking>` traces appear inside collapsible drawers, and token/cost counters update in real time.
5. **Human-in-the-Loop:** If a tool fails consecutively ($N=3$) or a budget is exceeded, the node safely pauses in `WAITING_OPERATOR` for you to resolve using `/retry` or `/cancel`.

---

### Mode 2: Headless Scripting & Pipeline Execution

Use the `-p` / `--print` flag to execute a single prompt or slash command non-interactively and print the output directly to standard output:

#### Inspect the Skills Catalog Headlessly:
```bash
uv run neuri -p "/skills"
```

#### Check Workspace & Telemetry Status:
```bash
uv run neuri -p "/status"
```

#### Run a Single Research Prompt Headlessly:
```bash
uv run neuri -p "Inspect NIfTI header for /data/bids/sub-01/anat/sub-01_T1w.nii.gz"
```

#### CLI Options Summary:
```text
Usage: neuri [OPTIONS]

Options:
  -p, --print TEXT      Execute single prompt or slash command headlessly.
  -v, --version         Display Neuri version information.
  -w, --workspace PATH  Custom workspace directory path.
  --help                Show this message and exit.
```

---

## Project Workspace Structure (`.neuri/`)

Running `/init` creates a local `.neuri/` directory in your project root:

```text
my_neuro_project/
├── .neuri/
│   ├── neuri.toml              # Project-specific harness routing & budget overrides
│   ├── state.db                # SQLite WAL Blackboard (7 tables tracking DAG state)
│   ├── execution_history.json  # Append-only provenance graph of executed pipelines
│   ├── references.bib          # Anti-hallucination BibTeX ledger for cited tools
│   ├── qa_snapshots/           # Visual QA PNG/HTML bundles
│   └── skills/                 # Optional lab-custom SKILL.md extension packs
└── ...
```

### Configuration (`.neuri/neuri.toml`)

```toml
[project]
name = "my_neuro_project"
default_remote_host = "localhost"

[harnesses.routing]
default = "agy"
coordinator = "agy"
neuroimaging_specialist = "agy"
pipeline_engineer = "codex"
compute_operator = "codex"
critic_qa = "agy"
scientific_writer = "agy"

[budgets]
max_node_tokens = 64000
max_workflow_cost_usd = 10.00
consecutive_failure_threshold = 3
```

---

## Tier-0 Neuroscience Skills Catalog

Neuri includes a built-in, compact (<300 tokens) skill index in [`skills/index.yaml`](skills/index.yaml):

| Skill ID | Name | Modalities | Example Triggers |
| :--- | :--- | :--- | :--- |
| `bids-standard` | BIDS & Neuro File IO | T1w, T2w, bold, dwi, eeg, meg | `validate BIDS`, `inspect header`, `sanitize PHI` |
| `neuroimaging-preproc` | Structural MRI Preproc | T1w, T2w | `brain extraction`, `BET`, `recon-all`, `ANTs registration` |
| `fmri-postproc` | Functional MRI & GLM | bold | `fMRI preprocessing`, `GLM analysis`, `nuisance regression` |
| `dwi-tractography` | Diffusion MRI & Tractography | dwi, tractography | `eddy correction`, `FOD estimation`, `tckgen` |
| `eeg-meg-pipeline` | Electrophysiology (EEG/MEG) | eeg, meg, ieeg | `ICA cleaning`, `bad channels`, `time-frequency`, `MNE` |
| `remote-compute-slurm` | Remote HPC & Slurm | table, report_qa | `sbatch generation`, `GPU scheduling`, `sacct tracking` |
| `scientific-writing-neuro` | Scientific Writer & COBIDAS | table, report_qa | `PRISMA literature search`, `DOI validation`, `reproducible Methods` |

### Custom Lab Skills
To register internal lab toolboxes without modifying Neuri source code, simply create a folder in `.neuri/skills/<my_skill>/` containing a `SKILL.md` file. Neuri automatically discovers it and adds it to `/skills`.

---

## Testing & Quality Assurance

Neuri enforces strict coding standards (PEP 8, full type annotations, docstrings with `Parameters`/`Returns` sections, and zero global state).

To run all unit, adversarial, adapter replay, and Textual pilot tests:

```bash
uv run pytest -v
```

To run the automated standards AST compliance checker:

```bash
uv run pytest tests/unit/test_standards_compliance.py -v
```

---

## Architecture & Roadmap

For full engineering specifications and multi-phase implementation details:
- [Neuri Architecture & Implementation Plan](technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md)
- [Phase 1 Implementation Plan](technical_documenation/PHASE_1_IMPLEMENTATION_PLAN.md)
