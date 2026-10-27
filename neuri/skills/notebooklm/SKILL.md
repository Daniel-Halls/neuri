---
name: notebooklm
description: Interact with Google NotebookLM via the `nlm` CLI to manage notebooks, add sources, generate AI audio overviews, conduct web research, and query notebook collections.
triggers:
  - notebooklm
  - query notebook
  - create notebook
  - nlm
  - audio overview
modalities:
  - table
  - report_qa
---

# NotebookLM Skill

Operate Google NotebookLM through the `nlm` CLI tool. Use this skill to manage research notebooks, ingest sources, run AI queries over notebook collections, and generate audio or studio artifacts.

## Authentication & Verification

Before running operations, verify authentication:

```bash
nlm login --check
```

- If authenticated, proceed with requested tasks.
- If **not authenticated**, do **not** run `nlm login` directly in automated commands (it launches an interactive Chrome browser). Instead, prompt the user to run `nlm login` in their terminal and notify you when finished.

## Common Workflows

### 1. Notebook Management & Adding Sources
```bash
# List all existing notebooks
nlm notebook list

# Create a notebook and capture the notebook ID portably
NOTEBOOK_ID=$(nlm notebook create "Notebook Title" | awk -F': ' '/id:/ {print $2}')
```

Add sources to the notebook (always provide absolute paths for local files):
```bash
# Add web URL
nlm source add "$NOTEBOOK_ID" --url "https://example.com/article"

# Add YouTube video
nlm source add "$NOTEBOOK_ID" --url "https://youtube.com/watch?v=VIDEO_ID"

# Add local document (PDF, TXT, MD, etc.)
nlm source add "$NOTEBOOK_ID" --file "/absolute/path/to/document.pdf"

# Add raw text snippet
nlm source add "$NOTEBOOK_ID" --text "Paste raw content here"

# Import Google Drive document
nlm source add "$NOTEBOOK_ID" --drive "DRIVE_FILE_ID"
```

List sources in a notebook:
```bash
nlm source list "$NOTEBOOK_ID"
```

### 2. Query Notebooks (Q&A & Summarization)
Run grounded natural language queries against ingested sources:
```bash
nlm notebook query "$NOTEBOOK_ID" "What are the main findings and conclusions?"
```

### 3. Web Research & Ingestion
Execute automated topic research:
```bash
# Research and automatically import top results into a new notebook
nlm research start "Research topic query" --deep --import
```

### 4. Audio Podcasts & Studio Artifacts
Generate studio artifacts such as audio overviews:
```bash
# Initiate audio generation
nlm audio create "$NOTEBOOK_ID" --confirm
```

Checking status and downloading:
- Generation is asynchronous and takes time. Check status when needed:
  ```bash
  nlm studio list "$NOTEBOOK_ID"
  # Or check specific artifact:
  nlm studio status "$NOTEBOOK_ID" <artifact-id>
  ```
- **Do not poll in a tight loop.** Check status once and report progress to the user, or let the user know generation is in progress.
- Once completed, download the artifact:
  ```bash
  nlm download audio "$NOTEBOOK_ID" <artifact-id> --format mp3
  ```

### 5. Sharing & Collaboration
```bash
# Make notebook publicly accessible
nlm share public "$NOTEBOOK_ID"

# Disable public sharing
nlm share disable "$NOTEBOOK_ID"

# Invite a collaborator
nlm share invite "$NOTEBOOK_ID" --email "user@example.com" --role editor
```
