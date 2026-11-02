# Global Memory & Researcher Integration

1. **Always-On Background Memory (`basic-memory`):**
   - Neuri agents have continuous access to the `basic-memory` MCP server (`research` project) and the `notebooklm` skill.
   - During normal research DAG execution or interactive chat, query `search_notes` or `read_note` in `basic-memory` whenever past theoretical context, mathematical formulations, or literature priors are relevant.
   - When notable architectural, statistical, or methodological decisions are made, update or create the relevant note in `basic-memory`.

2. **Dedicated Commands:**
   - Slash command `/researcher <topic/question>` activates autonomous academic researcher mode.
   - Slash command `/paperback <instruction/text>` activates the scientific writer, 5-pass referee, and APA 7 citation engine.

3. **Cognitive Brain & Pipeline Documentation (`neuri_docs` MCP):**
   - Neuri maintains indexed technical manuals across 20+ MRI pipelines in SQLite FTS5.
   - Access this knowledge directly via the `neuri_docs` MCP server or CLI:
     - CLI flags & options: call `search_pipeline_commands(pipeline, query)`
     - Python APIs & functions: call `search_pipeline_functions(pipeline, query)`
     - Workflows & concepts: call `search_pipeline_docs(pipeline, query)`
     - Shell fallback: run `python -m neuri.docs.ingest.cli search <pipeline> <query>`
   - Formulate search queries intelligently using technical synonyms based on software implementation (e.g. search `carbon` or `power` for emissions).
   - Run a single targeted search query first. As soon as relevant flags or functions are retrieved, immediately output your answer. Do not inspect codebase files or probe database tables.
   - When querying pipeline documentation, do not invoke external literature search or attach academic citations unless explicitly requested.
