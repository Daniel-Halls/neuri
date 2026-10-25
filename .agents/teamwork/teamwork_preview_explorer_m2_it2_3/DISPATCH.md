## 2026-10-25T16:45:02Z
You are Explorer M2-It2 Citations.
Working directory: `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m2_it2_3/`
Read `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md` before starting work.
Read `/Users/mszdjh3/code/neuri/PROJECT.md`.
Read `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_challenger_m2_2/handoff.md` and `/Users/mszdjh3/code/neuri/tests/unit/test_adversarial_blackboard_provenance.py`.

Your mission:
Investigate and design the exact fix strategy for Observations 1.4 and 1.5 from Challenger M2-2:
1. Raw `sqlite3.IntegrityError` leaked on citation year boundary violation: wrap SQL execution in `register_citation` to catch `sqlite3.IntegrityError` and raise `BlackboardError` with clear diagnostic context.
2. BibTeX format validation in `register_citation`: validate that the `bibtex` string is non-empty and contains basic BibTeX entry syntax (e.g. `@` and `{ ... }`), rejecting malformed strings with `ValueError` or `BlackboardError` so `sync_citations_to_bib` cannot corrupt `references.bib`.
3. Verify impact on existing tests in `tests/unit/test_blackboard.py` and new tests in `tests/unit/test_adversarial_blackboard_provenance.py`.
Provide exact drop-in code snippets conforming 100% to Universal Python Standards (`/Users/mszdjh3/.gemini/config/rules/python_standard.md`).
Deliver your findings in `handoff.md` in your working directory and notify the orchestrator via `send_message`.
