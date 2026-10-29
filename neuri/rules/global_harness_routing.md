# Harness and Model Routing Rule

1. **Dynamic Harness Model Discovery (Never Hardcode Models):**
   - Models must never be hardcoded. Available models are always queried dynamically from the underlying harness CLI (`agy models`, `ollama list`, `codex`, `openclaw models list`, `opencode models`).

2. **Automatic Model Switching on Harness Change:**
   - Whenever the active harness changes (via `/harness <name>`, configuration reload, or session startup), Neuri automatically queries the target harness for its available models.
   - If the previously active model does not belong to the new harness's available models, Neuri automatically switches `default_model` and all `harness_routing` role models to the first available model on the new harness and persists the updated configuration.
   - Prompts and DAG nodes must never be routed to a model belonging to a different harness.
