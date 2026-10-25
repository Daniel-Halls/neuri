# BRIEFING — 2026-10-25T15:16:15Z

## Mission
Analyze and specify the exact implementation strategy for pyproject.toml packaging and skills/index.yaml (<300 tokens) for Milestone 1.

## 🔒 My Identity
- Archetype: explorer
- Roles: explorer, investigator, synthesizer
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_1/
- Original parent: 93d2f271-2e53-4e5d-a816-275a3ea34195
- Milestone: M1 (Packaging and Compact Catalog)

## 🔒 Key Constraints
- Read-only investigation — do NOT implement / do NOT modify source code files
- pyproject.toml must use hatchling backend, Python >=3.12, strict dependencies, typer CLI entrypoint, ruff and mypy configurations
- skills/index.yaml must index 7 neuroscience skill packs strictly within <300 token budget
- Adhere to Python coding standards and PEP 8 guidelines
- Deliver comprehensive handoff report at handoff.md and notify orchestrator

## Current Parent
- Conversation ID: 93d2f271-2e53-4e5d-a816-275a3ea34195
- Updated: 2026-10-25T15:19:30Z

## Investigation State
- **Explored paths**:
  - `ORIGINAL_REQUEST.md`: R1 package scaffolding, dependencies, skills/index.yaml (<300 tokens)
  - `PROJECT.md`: M1 scope, features 16 (Compact Catalog) & 17 (pyproject.toml), layout
  - `technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md`: sections 3.5, 6, 7
  - `rules/python_standard.md`: PEP 8, typing, docstring templates, zero globals
  - `spec_miner_survey_1/handoff.md`, `spec_miner_survey_2/handoff.md`, `explorer_survey_3/handoff.md`
- **Key findings**:
  - Repository is greenfield (no `pyproject.toml`, no `src/`, no `skills/`).
  - `pyproject.toml` requires `hatchling` backend, Python `>=3.12`, all 10 core dependencies + ruff/mypy configs, `[project.scripts]` entrypoint `neuri = "neuri.cli.main:app"`, and wheel package path `src/neuri`.
  - `skills/index.yaml` requires indexing 7 neuroscience skill packs (`bids-standard`, `neuroimaging-preproc`, `fmri-postproc`, `dwi-tractography`, `eeg-meg-pipeline`, `remote-compute-slurm`, `scientific-writing-neuro`) under strict <300 token budget.
  - Ultra-compact catalog formulation achieves ~215-225 tokens (142 words, 1,280 characters), well under the 300 token budget.
- **Unexplored areas**: None for M1-1 scope.

## Key Decisions Made
- Use standard PEP 621 metadata with Hatchling wheel packaging `packages = ["src/neuri"]`.
- Include both `[project.optional-dependencies]` and `[dependency-groups]` for maximum compatibility (`uv sync --all-extras`, `pip install -e ".[dev]"`).
- Include strict `[tool.ruff]`, `[tool.mypy]`, and `[tool.pytest.ini_options]` with `asyncio_default_fixture_loop_scope = "function"`.
- Provide both Candidate A and Candidate B for `skills/index.yaml` with exact token count breakdown and automated token test fixture.

## Artifact Index
- /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_1/DISPATCH.md — Task assignment
- /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_1/BRIEFING.md — Persistent memory
- /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_1/progress.md — Liveness tracker
- /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_1/handoff.md — Final handoff report (to be written)

