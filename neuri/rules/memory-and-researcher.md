# Global Memory & Researcher Integration

1. **Always-On Background Memory (`basic-memory`):**
   - Neuri agents have continuous access to the `basic-memory` MCP server (`research` project) and the `notebooklm` skill.
   - During normal research DAG execution or interactive chat, query `search_notes` or `read_note` in `basic-memory` whenever past theoretical context, mathematical formulations, or literature priors are relevant.
   - When notable architectural, statistical, or methodological decisions are made, update or create the relevant note in `basic-memory`.

2. **Dedicated Commands:**
   - Slash command `/researcher <topic/question>` activates autonomous academic researcher mode.
   - Slash command `/paperback <instruction/text>` activates the scientific writer, 5-pass referee, and APA 7 citation engine.
