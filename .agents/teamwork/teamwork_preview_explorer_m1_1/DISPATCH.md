# Task Assignment: M1 Exploration - Packaging & Compact Catalog

## Identity
- Role: Explorer M1-1
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_1/
- Project root: /Users/mszdjh3/code/neuri

## Objective
Analyze and recommend the exact implementation strategy for:
1. `pyproject.toml` with `hatchling` backend, Python `>=3.12`, all dependencies (`pydantic>=2.7`, `typer>=0.12`, `rich>=13.7`, `textual>=0.80`, `pyyaml>=6.0`, `tomli-w>=1.0`, `httpx>=0.27`, `pytest>=8.2`, `pytest-asyncio>=0.24`, `pytest-mock>=3.14`), scripts (`neuri = "neuri.cli.main:app"`), and ruff/mypy tool configs.
2. `skills/index.yaml`: Tier-0 compact catalog indexing 7 neuroscience skill packs (`bids-standard`, `neuroimaging-preproc`, `fmri-postproc`, `dwi-tractography`, `eeg-meg-pipeline`, `remote-compute-slurm`, `scientific-writing-neuro`) adhering strictly to the <300 token budget.

## Mandatory Inputs to Read
1. `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md`
2. `/Users/mszdjh3/code/neuri/PROJECT.md`
3. `/Users/mszdjh3/code/neuri/technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md`
4. `/Users/mszdjh3/.gemini/config/rules/python_standard.md`
5. `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_spec_miner_survey_1/handoff.md`

## Output Requirements
Write `handoff.md` in your working directory with concrete file content specifications, token count calculations, and verification steps.

## 2026-10-25T15:15:47Z
From: 93d2f271-2e53-4e5d-a816-275a3ea34195
You are explorer_m1_1.
Your working directory is: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_1/
Please read your task assignment at: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_1/DISPATCH.md
Also read:
1. /Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md
2. /Users/mszdjh3/code/neuri/PROJECT.md
3. /Users/mszdjh3/code/neuri/technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md
4. /Users/mszdjh3/.gemini/config/rules/python_standard.md
5. /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_spec_miner_survey_1/handoff.md

Focus on pyproject.toml packaging and skills/index.yaml (<300 tokens).
Write your detailed findings to /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_1/handoff.md and notify the orchestrator when done.
Do not modify source code files.
