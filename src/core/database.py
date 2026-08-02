"""
SQLite Database & Job Persistence Engine
Provides durable persistence for jobs, agent trace histories, quality audits, and outputs.
"""

import sqlite3
import json
import os
import time
from typing import Dict, Any, List, Optional
from src.core.models import PipelineContext


class DatabaseEngine:
    """SQLite Persistence Engine for jobs, trace logs, and generated artifacts."""

    def __init__(self, db_path: str = "./output/db.sqlite3"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    raw_topic TEXT,
                    stage TEXT,
                    start_time REAL,
                    end_time REAL,
                    plagiarism_pct REAL,
                    ai_pct REAL,
                    upskill_score REAL,
                    pdf_path TEXT,
                    pptx_path TEXT,
                    created_at REAL,
                    job_mode TEXT,
                    writer_mode TEXT,
                    manuscript_preview TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT,
                    agent_name TEXT,
                    layer INTEGER,
                    content TEXT,
                    level TEXT,
                    timestamp REAL
                )
            """)
            # Lightweight migrations for older DBs
            cols = {r[1] for r in cursor.execute("PRAGMA table_info(jobs)").fetchall()}
            for col, decl in (
                ("job_mode", "TEXT"),
                ("writer_mode", "TEXT"),
                ("manuscript_preview", "TEXT"),
            ):
                if col not in cols:
                    cursor.execute(f"ALTER TABLE jobs ADD COLUMN {col} {decl}")
            conn.commit()

    def save_job(self, ctx: PipelineContext):
        preview = (ctx.output.markdown_manuscript or "")[:4000]
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO jobs (
                    job_id, raw_topic, stage, start_time, end_time,
                    plagiarism_pct, ai_pct, upskill_score, pdf_path, pptx_path,
                    created_at, job_mode, writer_mode, manuscript_preview
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    stage=excluded.stage,
                    end_time=excluded.end_time,
                    plagiarism_pct=excluded.plagiarism_pct,
                    ai_pct=excluded.ai_pct,
                    upskill_score=excluded.upskill_score,
                    pdf_path=excluded.pdf_path,
                    pptx_path=excluded.pptx_path,
                    job_mode=excluded.job_mode,
                    writer_mode=excluded.writer_mode,
                    manuscript_preview=excluded.manuscript_preview
            """, (
                ctx.job_id,
                ctx.raw_topic,
                ctx.stage.value,
                ctx.start_time,
                ctx.end_time or time.time(),
                ctx.quality_audit.plagiarism_percentage,
                ctx.quality_audit.ai_writing_percentage,
                ctx.quality_audit.upskill_accuracy_score,
                ctx.output.pdf_path,
                ctx.output.pptx_path,
                time.time(),
                getattr(ctx, "job_mode", "full_paper"),
                getattr(ctx, "writer_mode", "multi"),
                preview,
            ))
            conn.commit()

    def log_agent_event(self, job_id: str, agent_name: str, layer: int, content: str, level: str = "INFO"):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO agent_logs (job_id, agent_name, layer, content, level, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (job_id, agent_name, layer, content, level, time.time()))
            conn.commit()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_recent_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_job_logs(self, job_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT agent_name, layer, content, level, timestamp FROM agent_logs "
                "WHERE job_id = ? ORDER BY id DESC LIMIT ?",
                (job_id, limit),
            )
            rows = [dict(r) for r in cursor.fetchall()]
            rows.reverse()
            return rows
