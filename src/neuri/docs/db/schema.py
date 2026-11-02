"""SQLite database schema and DDL definitions for Neuri documentation vault.

Defines tables for pipelines, documentation entries across commands, functions,
and documentation types, and full-text search indexes with FTS5.
"""

class DocsDBSchema:
    """SQLite database schema and DDL definitions for Neuri documentation vault.

    Defines tables for pipelines, documentation entries across commands,
    functions, and documentation types, and full-text search indexes with FTS5.
    """

    DDL_SCRIPT: str = """
CREATE TABLE IF NOT EXISTS pipelines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    aliases TEXT NOT NULL DEFAULT '[]',
    has_commands INTEGER NOT NULL DEFAULT 0,
    has_functions INTEGER NOT NULL DEFAULT 0,
    has_documentation INTEGER NOT NULL DEFAULT 0,
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS doc_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_id INTEGER NOT NULL REFERENCES pipelines(id) ON DELETE CASCADE,
    pipeline_name TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    section_title TEXT NOT NULL,
    item_name TEXT NOT NULL,
    content TEXT NOT NULL,
    source_file TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_doc_entries_pipeline_type
ON doc_entries (pipeline_name, doc_type);

CREATE VIRTUAL TABLE IF NOT EXISTS doc_entries_fts USING fts5(
    pipeline_name,
    doc_type UNINDEXED,
    section_title,
    item_name,
    content,
    tokenize="porter unicode61 tokenchars '-_.'"
);

CREATE TRIGGER IF NOT EXISTS trg_doc_entries_ai AFTER INSERT ON doc_entries BEGIN
    INSERT INTO doc_entries_fts(
        rowid, pipeline_name, doc_type, section_title, item_name, content
    ) VALUES (
        new.id, new.pipeline_name, new.doc_type, new.section_title,
        new.item_name, new.content
    );
END;

CREATE TRIGGER IF NOT EXISTS trg_doc_entries_ad AFTER DELETE ON doc_entries BEGIN
    DELETE FROM doc_entries_fts WHERE rowid = old.id;
END;
"""


__all__: list[str] = [
    "DocsDBSchema",
]
