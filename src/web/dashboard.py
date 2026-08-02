"""
Layer 7: Real-Time Web Dashboard & REST API Visualizer
FastAPI server serving live multi-agent execution visualizers, SSE event logs, and job management.
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
import asyncio
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import time
import shutil
import uuid
from typing import Dict, Any, List, Optional
from src.core.models import PipelineContext
from src.core.database import DatabaseEngine
from src.core.progress import progress_payload
from src.agents.layer6_supervisor import SupervisorAgent

UPLOAD_ROOT = os.path.abspath("./output/uploads")
os.makedirs(UPLOAD_ROOT, exist_ok=True)

app = FastAPI(
    title="Autonomous Research Companion (ARC) Dashboard",
    description="Layer 7 Interactive Multi-Agent Research System & Visualizer",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = DatabaseEngine()
supervisor = SupervisorAgent()
active_pipeline_jobs: Dict[str, PipelineContext] = {}
active_websockets: List[WebSocket] = []
main_loop = None

@app.on_event("startup")
async def startup_event():
    global main_loop
    main_loop = asyncio.get_running_loop()

async def _broadcast_log(msg: Any):
    log_data = {
        "agent": msg.agent_name,
        "layer": msg.layer,
        "content": msg.content,
        "level": msg.level,
        "time": msg.timestamp
    }
    dead = []
    for ws in active_websockets:
        try:
            await ws.send_json(log_data)
        except Exception:
            dead.append(ws)
    for w in dead:
        if w in active_websockets:
            active_websockets.remove(w)

def sync_broadcast_log(msg: Any):
    if main_loop and main_loop.is_running():
        asyncio.run_coroutine_threadsafe(_broadcast_log(msg), main_loop)
    # Persist log lines for job history
    try:
        # Find job_id from active jobs by matching latest agent message timing is hard;
        # store against all active incomplete jobs that have this as last log — skip if unclear.
        for jid, ctx in list(active_pipeline_jobs.items()):
            if ctx.logs and ctx.logs[-1] is msg:
                db.log_agent_event(jid, msg.agent_name, int(msg.layer) if msg.layer else 0, msg.content, msg.level)
                db.save_job(ctx)
                break
    except Exception:
        pass

supervisor.bus.subscribe(sync_broadcast_log)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)


def run_pipeline_async(ctx: PipelineContext):
    completed_ctx = supervisor.execute_pipeline(ctx, output_dir="./output")
    db.save_job(completed_ctx)
    active_pipeline_jobs[ctx.job_id] = completed_ctx


@app.post("/api/jobs")
def create_job(payload: Dict[str, Any], background_tasks: BackgroundTasks):
    job_id = f"job_{int(time.time())}"
    raw_topic = payload.get("raw_topic", "Multi-Agent Autonomous Systems")
    raw_code = list(payload.get("raw_code_paths") or [])
    raw_notes = list(payload.get("raw_notes_paths") or [])
    github_url = (payload.get("github_url") or "").strip() or None
    job_mode = (payload.get("job_mode") or "full_paper").strip().lower()
    writer_mode = (payload.get("writer_mode") or "multi").strip().lower()
    selected_writers = payload.get("selected_writers") or []
    if isinstance(selected_writers, str):
        selected_writers = [w.strip() for w in selected_writers.split(",") if w.strip()]
    draft_text = payload.get("draft_text") or ""
    target_section = payload.get("target_section") or None

    # Normalize empty local paths
    raw_code = [p for p in raw_code if p and str(p).strip()]
    raw_notes = [p for p in raw_notes if p and str(p).strip()]
    if github_url and github_url not in raw_code:
        raw_code.append(github_url)

    # Mode defaults
    if job_mode == "literature_review" and not selected_writers and writer_mode == "multi":
        selected_writers = ["Literature Review"]
        target_section = target_section or "Literature Review"
    if job_mode == "complete_draft":
        writer_mode = "single"
    if job_mode in ("literature_review", "research_only") and not raw_code and not github_url:
        skip_code = True
    else:
        skip_code = bool(payload.get("skip_code_analysis", False))

    allowed_modes = {"full_paper", "literature_review", "research_only", "complete_draft"}
    if job_mode not in allowed_modes:
        raise HTTPException(status_code=400, detail=f"job_mode must be one of {sorted(allowed_modes)}")
    if writer_mode not in {"multi", "single"}:
        raise HTTPException(status_code=400, detail="writer_mode must be multi or single")
    if job_mode == "complete_draft" and not draft_text.strip():
        raise HTTPException(status_code=400, detail="complete_draft requires draft_text")

    ctx = PipelineContext(
        job_id=job_id,
        raw_topic=raw_topic,
        raw_code_paths=raw_code,
        raw_notes_paths=raw_notes,
        github_url=github_url,
        job_mode=job_mode,
        writer_mode=writer_mode,
        selected_writers=selected_writers,
        draft_text=draft_text,
        target_section=target_section,
        skip_code_analysis=skip_code,
    )
    active_pipeline_jobs[job_id] = ctx
    db.save_job(ctx)

    background_tasks.add_task(run_pipeline_async, ctx)
    return {
        "status": "SUCCESS",
        "job_id": job_id,
        "job_mode": job_mode,
        "writer_mode": writer_mode,
        "message": "Pipeline execution started in background",
    }


@app.get("/api/options")
def job_options():
    """Dashboard selectors: modes and writer agents."""
    return {
        "job_modes": [
            {"id": "full_paper", "label": "Full research paper"},
            {"id": "literature_review", "label": "Literature review only"},
            {"id": "research_only", "label": "Research findings only (no full paper)"},
            {"id": "complete_draft", "label": "Complete half-written paper"},
        ],
        "writer_modes": [
            {"id": "multi", "label": "Multiple section writers"},
            {"id": "single", "label": "One writer agent only"},
        ],
        "writer_agents": [
            "Abstract",
            "Introduction",
            "Literature Review",
            "Proposed Method / Methodology",
            "System Architecture",
            "Algorithm / Flowchart",
            "Results",
            "Discussion",
            "Conclusion",
            "Generic (single full draft)",
        ],
    }


@app.post("/api/upload")
async def upload_files(
    kind: str = Form("code"),
    files: List[UploadFile] = File(...),
):
    """Upload code (.py/.c/.cpp/.js/…) or notes (.pdf/.txt/.md). Returns saved paths."""
    kind = (kind or "code").lower()
    if kind not in ("code", "notes"):
        raise HTTPException(status_code=400, detail="kind must be code or notes")
    batch = f"up_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    dest_dir = os.path.join(UPLOAD_ROOT, batch)
    os.makedirs(dest_dir, exist_ok=True)
    saved = []
    for f in files:
        name = os.path.basename(f.filename or "upload.bin")
        path = os.path.join(dest_dir, name)
        with open(path, "wb") as out:
            shutil.copyfileobj(f.file, out)
        saved.append(path)
    return {"status": "SUCCESS", "kind": kind, "paths": saved, "batch": batch}


@app.get("/api/jobs/{job_id}/manuscript")
def get_manuscript(job_id: str):
    if job_id in active_pipeline_jobs:
        ctx = active_pipeline_jobs[job_id]
        return {
            "job_id": job_id,
            "markdown": ctx.output.markdown_manuscript or "",
            "draft_text": ctx.draft_text or "",
        }
    row = db.get_job(job_id)
    if row:
        return {
            "job_id": job_id,
            "markdown": row.get("manuscript_preview") or "",
            "draft_text": "",
        }
    raise HTTPException(status_code=404, detail="Job not found")


@app.get("/api/jobs")
def list_jobs():
    return {"jobs": db.list_recent_jobs(30)}


@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: str):
    if job_id in active_pipeline_jobs:
        ctx = active_pipeline_jobs[job_id]
        payload = {
            "job_id": ctx.job_id,
            "raw_topic": ctx.raw_topic,
            "stage": ctx.stage.value,
            "plagiarism_pct": ctx.quality_audit.plagiarism_percentage,
            "ai_pct": ctx.quality_audit.ai_writing_percentage,
            "upskill_score": ctx.quality_audit.upskill_accuracy_score,
            "is_estimate": ctx.quality_audit.is_estimate,
            "qa_method": ctx.quality_audit.qa_method,
            "is_approved": ctx.quality_audit.is_approved,
            "rejection_reasons": ctx.quality_audit.rejection_reasons,
            "pdf_path": ctx.output.pdf_path,
            "pptx_path": ctx.output.pptx_path,
            "reviewer_answers": ctx.quality_audit.reviewer_answers,
            "logs_count": len(ctx.logs),
            "job_mode": ctx.job_mode,
            "writer_mode": ctx.writer_mode,
            "manuscript_preview": (ctx.output.markdown_manuscript or "")[:2000],
            "has_pdf": bool(ctx.output.pdf_path and os.path.exists(ctx.output.pdf_path or "")),
            "has_pptx": bool(ctx.output.pptx_path and os.path.exists(ctx.output.pptx_path or "")),
        }
        payload.update(progress_payload(ctx))
        return payload

    job_data = db.get_job(job_id)
    if job_data:
        job_data = dict(job_data)
        job_data["has_pdf"] = bool(job_data.get("pdf_path") and os.path.exists(job_data["pdf_path"] or ""))
        job_data["has_pptx"] = bool(job_data.get("pptx_path") and os.path.exists(job_data["pptx_path"] or ""))
        job_data["current_agent"] = ""
        job_data["progress_pct"] = 100.0 if job_data.get("stage") == "COMPLETED" else 0
        job_data["eta_seconds"] = 0 if job_data.get("stage") == "COMPLETED" else None
        return job_data
    raise HTTPException(status_code=404, detail="Job not found")


@app.get("/api/jobs/{job_id}/logs")
def get_job_logs(job_id: str):
    if job_id in active_pipeline_jobs:
        logs = [
            {
                "agent": msg.agent_name,
                "layer": msg.layer,
                "content": msg.content,
                "level": msg.level,
                "time": msg.timestamp
            }
            for msg in active_pipeline_jobs[job_id].logs
        ]
        return {"job_id": job_id, "logs": logs}
    return {"job_id": job_id, "logs": db.get_job_logs(job_id)}


@app.get("/download/pdf/{job_id}")
def download_pdf(job_id: str):
    candidates = [
        f"./output/{job_id}_ResearchPaper.pdf",
        f"./output/ResearchPaper.pdf",
    ]
    if job_id in active_pipeline_jobs and active_pipeline_jobs[job_id].output.pdf_path:
        candidates.insert(0, active_pipeline_jobs[job_id].output.pdf_path)
    for pdf_file in candidates:
        if pdf_file and os.path.exists(pdf_file):
            return FileResponse(pdf_file, media_type="application/pdf", filename=f"ResearchPaper_{job_id}.pdf")
    raise HTTPException(status_code=404, detail="PDF not generated yet")


@app.get("/download/pptx/{job_id}")
def download_pptx(job_id: str):
    candidates = [
        f"./output/{job_id}_Presentation.pptx",
        f"./output/Presentation.pptx",
    ]
    if job_id in active_pipeline_jobs and active_pipeline_jobs[job_id].output.pptx_path:
        candidates.insert(0, active_pipeline_jobs[job_id].output.pptx_path)
    for pptx_file in candidates:
        if pptx_file and os.path.exists(pptx_file):
            return FileResponse(
                pptx_file,
                media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                filename=f"Presentation_{job_id}.pptx",
            )
    raise HTTPException(status_code=404, detail="PPTX not generated yet")


@app.get("/nn", response_class=HTMLResponse)
async def serve_nn_ui():
    """Serve the 3D Neural Topology UI"""
    with open(os.path.join(os.path.dirname(__file__), "static", "nn.html")) as f:
        return f.read()

@app.get("/nn2d", response_class=HTMLResponse)
async def serve_nn2d_ui():
    """Serve the 2D Neural Topology UI"""
    with open(os.path.join(os.path.dirname(__file__), "static", "nn_2d.html")) as f:
        return f.read()

@app.get("/", response_class=HTMLResponse)
def render_dashboard():
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Autonomous Research Companion — Research Pipeline Control Center</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0f172a;
            --card-bg: #1e293b;
            --accent: #8b5cf6;
            --accent-green: #10b981;
            --accent-blue: #3b82f6;
            --text: #f8fafc;
            --text-dim: #94a3b8;
            --border: #334155;
        }
        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 24px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            padding-bottom: 16px;
            margin-bottom: 24px;
        }
        .title h1 {
            margin: 0;
            font-size: 24px;
            color: var(--text);
            background: linear-gradient(135deg, #a78bfa, #3b82f6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .grid {
            display: grid;
            grid-template-columns: 1fr 2fr;
            gap: 20px;
        }
        .card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3);
        }
        .card h2 {
            font-size: 16px;
            margin-top: 0;
            color: var(--accent-blue);
            border-bottom: 1px solid var(--border);
            padding-bottom: 8px;
        }
        label {
            display: block;
            font-size: 12px;
            color: var(--text-dim);
            margin-top: 12px;
            margin-bottom: 4px;
        }
        input, select, textarea {
            width: 100%;
            padding: 10px;
            background: #0f172a;
            border: 1px solid var(--border);
            border-radius: 6px;
            color: white;
            font-size: 14px;
            box-sizing: border-box;
            font-family: inherit;
        }
        textarea { resize: vertical; min-height: 140px; }
        .dropzone {
            border: 1px dashed var(--border);
            border-radius: 8px;
            padding: 14px;
            text-align: center;
            color: var(--text-dim);
            font-size: 12px;
            margin-top: 8px;
            background: #0b1220;
            cursor: pointer;
        }
        .dropzone.dragover { border-color: var(--accent); color: #fff; }
        .progress-wrap {
            background: #0b1220;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 12px;
            margin-top: 12px;
        }
        .progress-bar {
            height: 8px;
            background: #1e293b;
            border-radius: 4px;
            overflow: hidden;
            margin: 8px 0;
        }
        .progress-fill {
            height: 100%;
            width: 0%;
            background: linear-gradient(90deg, var(--accent), var(--accent-blue));
            transition: width 0.4s ease;
        }
        .history-item {
            display: flex;
            justify-content: space-between;
            gap: 8px;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid var(--border);
            font-size: 12px;
        }
        .history-item button {
            width: auto;
            margin: 0;
            padding: 6px 10px;
            font-size: 11px;
        }
        .draft-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin-top: 8px;
        }
        .draft-pane {
            background: #0b1220;
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 8px;
            max-height: 180px;
            overflow: auto;
            font-size: 11px;
            white-space: pre-wrap;
            color: var(--text-dim);
        }
        .chip {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 999px;
            background: #1e293b;
            border: 1px solid var(--border);
            font-size: 10px;
            margin: 2px;
            cursor: pointer;
        }
        .chip.active { border-color: var(--accent); color: #fff; }
        button {
            width: 100%;
            margin-top: 16px;
            padding: 12px;
            background: linear-gradient(135deg, var(--accent), var(--accent-blue));
            border: none;
            border-radius: 6px;
            color: white;
            font-weight: 600;
            cursor: pointer;
            transition: opacity 0.2s;
        }
        button:hover { opacity: 0.9; }
        .log-box {
            background: #090d16;
            border: 1px solid var(--border);
            border-radius: 8px;
            height: 380px;
            overflow-y: auto;
            padding: 12px;
            font-family: monospace;
            font-size: 12px;
            line-height: 1.6;
        }
        .log-entry {
            margin-bottom: 6px;
            border-bottom: 1px solid #1e293b;
            padding-bottom: 4px;
        }
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: bold;
            margin-right: 6px;
        }
        .badge-info { background: #3b82f6; color: white; }
        .badge-success { background: #10b981; color: white; }
        .badge-warn { background: #f59e0b; color: white; }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin-bottom: 16px;
        }
        .metric-card {
            background: #090d16;
            border: 1px solid var(--border);
            padding: 12px;
            border-radius: 8px;
            text-align: center;
        }
        .metric-value {
            font-size: 20px;
            font-weight: bold;
            color: var(--accent-green);
        }
        .metric-label {
            font-size: 11px;
            color: var(--text-dim);
        }
    </style>
</head>
<body>

    <div class="header">
        <div class="title">
            <h1>Autonomous Research Companion (ARC)</h1>
            <span style="font-size: 12px; color: var(--text-dim);">LangGraph multi-agent research pipeline — Heuristic QA (approximate)</span>
        </div>
        <div>
            <span class="badge badge-success">System Operational</span>
            <span class="badge badge-info">Heuristic QA</span>
        </div>
    </div>

    <div class="metrics-grid" style="grid-template-columns: repeat(5, 1fr);">
        <div class="metric-card">
            <div class="metric-value" id="m-faculty">Active</div>
            <div class="metric-label">Inst. Grounding</div>
        </div>
        <div class="metric-card">
            <div class="metric-value" id="m-plagiarism">—</div>
            <div class="metric-label">Plagiarism (heuristic)</div>
        </div>
        <div class="metric-card">
            <div class="metric-value" id="m-ai">—</div>
            <div class="metric-label">AI-style (heuristic)</div>
        </div>
        <div class="metric-card">
            <div class="metric-value" id="m-accuracy">—</div>
            <div class="metric-label">Upskill (estimate)</div>
        </div>
        <div class="metric-card">
            <div class="metric-value" id="m-status">IDLE</div>
            <div class="metric-label">Pipeline Stage</div>
        </div>
    </div>

    <div class="card" style="margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 8px; margin-bottom: 12px;">
            <h2 style="border: none; padding: 0; margin: 0; color: #a78bfa;">Pipeline Topology (LangGraph)</h2>
            <div style="display:flex; gap: 8px;">
                <span class="badge" style="background:#10b981; color:white;">Ingest</span>
                <span class="badge" style="background:#ef4444; color:white;">Research</span>
                <span class="badge" style="background:#f59e0b; color:white;">Write + Heuristic QA</span>
            </div>
        </div>
        <div id="d3-nn-container" style="width: 100%; height: 320px; background: #090d16; border-radius: 8px; border: 1px solid var(--border); overflow: hidden;"></div>
    </div>

    <div class="grid">
        <div class="card">
            <h2>Launch Research Pipeline</h2>

            <label>What do you want to do?</label>
            <select id="job_mode" onchange="onModeChange()">
                <option value="full_paper">Full research paper</option>
                <option value="literature_review">Literature review only</option>
                <option value="research_only">Research findings only</option>
                <option value="complete_draft">Complete half-written paper</option>
            </select>

            <label>Research Topic</label>
            <input type="text" id="topic" value="High-Performance Multi-Agent Event-Driven Systems">

            <label>GitHub / GitLab repo URL (optional)</label>
            <input type="text" id="github_url" placeholder="https://github.com/org/repo">

            <label>Or upload source code files</label>
            <div class="dropzone" id="dz-code" onclick="document.getElementById('file-code').click()">
                Drop code files here or click to browse
                <input type="file" id="file-code" multiple hidden accept=".py,.c,.cpp,.h,.js,.ts,.java,.go,.rs,.txt">
            </div>
            <div id="code-uploads" style="font-size:11px;color:var(--text-dim);margin-top:4px;"></div>
            <label>Local source code path (optional)</label>
            <input type="text" id="code" placeholder="./sample_data/sample_code.py">

            <label>Or upload PDF / notes</label>
            <div class="dropzone" id="dz-notes" onclick="document.getElementById('file-notes').click()">
                Drop PDF/TXT/MD here or click to browse
                <input type="file" id="file-notes" multiple hidden accept=".pdf,.txt,.md,.markdown">
            </div>
            <div id="notes-uploads" style="font-size:11px;color:var(--text-dim);margin-top:4px;"></div>
            <label>PDF / notes path (optional)</label>
            <input type="text" id="notes" placeholder="./sample_data/sample_notes.txt">

            <div id="writer-controls">
                <label>Writing agents</label>
                <select id="writer_mode" onchange="onWriterModeChange()">
                    <option value="multi">Multiple section writers</option>
                    <option value="single">One writer agent only</option>
                </select>

                <label id="writer-agent-label">Select writer agent(s)</label>
                <select id="writer_agents" multiple size="6" style="height:auto; min-height:120px;">
                    <option value="Abstract">Abstract</option>
                    <option value="Introduction">Introduction</option>
                    <option value="Literature Review" selected>Literature Review</option>
                    <option value="Proposed Method / Methodology">Methodology</option>
                    <option value="System Architecture">System Architecture</option>
                    <option value="Algorithm / Flowchart">Algorithm</option>
                    <option value="Results">Results</option>
                    <option value="Discussion">Discussion</option>
                    <option value="Conclusion">Conclusion</option>
                </select>
                <div style="font-size:11px; color:var(--text-dim); margin-top:4px;">
                    Multi: Ctrl/Cmd-click several. Single: first selected agent (or Generic if none).
                </div>
            </div>

            <div id="draft-box" style="display:none;">
                <label>Draft editor (half-written paper)</label>
                <textarea id="draft_text" rows="8" placeholder="Paste draft markdown / text here..." oninput="refreshDraftPreview()"></textarea>
                <div id="draft-section-chips" style="margin-top:6px;"></div>
                <div class="draft-grid">
                    <div>
                        <div style="font-size:11px;color:var(--text-dim);margin-bottom:4px;">Selected section</div>
                        <div class="draft-pane" id="draft-section-view">—</div>
                    </div>
                    <div>
                        <div style="font-size:11px;color:var(--text-dim);margin-bottom:4px;">Continuation hint</div>
                        <div class="draft-pane" id="draft-continue-hint">Writer continues from the end of your draft.</div>
                    </div>
                </div>
            </div>

            <div class="progress-wrap">
                <div style="display:flex;justify-content:space-between;font-size:12px;">
                    <span>Agent: <b id="m-agent">—</b></span>
                    <span>ETA: <b id="m-eta">—</b></span>
                </div>
                <div class="progress-bar"><div class="progress-fill" id="m-progress"></div></div>
                <div style="font-size:11px;color:var(--text-dim);">Stage: <span id="m-stage-detail">IDLE</span> · <span id="m-progress-label">0%</span></div>
            </div>

            <button onclick="startPipeline()">Run Pipeline</button>

            <div style="margin-top: 20px;">
                <h2>Generated Artifacts</h2>
                <button onclick="downloadPDF()" style="background: #2563eb; margin-bottom: 8px;">Download PDF</button>
                <button onclick="downloadPPTX()" style="background: #d97706; margin-bottom: 8px;">Download PPTX</button>
                <button onclick="loadManuscriptPreview()" style="background: #0ea5e9;">Preview manuscript</button>
                <div class="draft-pane" id="manuscript-preview" style="margin-top:8px;max-height:220px;">—</div>
            </div>

            <div style="margin-top: 20px;">
                <h2>Job History</h2>
                <button onclick="loadJobHistory()" style="background:#334155;margin-bottom:8px;">Refresh history</button>
                <div id="job-history"></div>
            </div>
        </div>

        <div class="card">
            <h2>Real-Time Agent Event Log</h2>
            <div class="log-box" id="log-box">
                <div class="log-entry"><span class="badge badge-info">SYSTEM</span> LangGraph supervisor ready. Heuristic QA enabled.</div>
            </div>
        </div>
    </div>

    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script>
        let currentJobId = null;
        let uploadedCodePaths = [];
        let uploadedNotesPaths = [];
        let draftSections = [];
        let selectedDraftSection = 0;
        let pollTimer = null;


        function initD3() {
            const d3Container = d3.select("#d3-nn-container");
            if (!d3Container.node()) return;
            const width = d3Container.node().getBoundingClientRect().width || 800;
            const height = 320;
            d3Container.selectAll("*").remove();
            const svg = d3Container.append("svg")
                .attr("width", "100%").attr("height", height)
                .attr("viewBox", `0 0 ${width} ${height}`);
            const architecture = [
                { layer: 0, name: 'L0', agents: ['RPA'], type: 'profiler' },
                { layer: 1, name: 'L1', agents: ['GI','CI','DI','SA','QP'], type: 'mamba' },
                { layer: 2, name: 'L2', agents: ['CB','AD','CA','HM','BE'], type: 'transformer' },
                { layer: 3, name: 'L3', agents: ['WSA','AA','CSA','LA','GF','FPA'], type: 'mamba' },
                { layer: 4, name: 'L4', agents: ['Conn','OB','Cit','Crit'], type: 'transformer' },
                { layer: 4.5, name: 'L4.5', agents: ['PC','AI','PRV','FQA'], type: 'transformer' },
                { layer: 5, name: 'L5', agents: ['WA','PDF','PPT'], type: 'mamba' },
                { layer: 6, name: 'L6', agents: ['Sup'], type: 'supervisor' }
            ];
            let nodes = [];
            const layerSpacing = width / (architecture.length + 1);
            const nodeSpacing = (height - 60) / 7;
            architecture.forEach((layerData, i) => {
                const numAgents = layerData.agents.length;
                const startY = (height - (numAgents - 1) * nodeSpacing) / 2 + 10;
                layerData.agents.forEach((agent, j) => {
                    nodes.push({ x: layerSpacing * (i + 1), y: startY + j * nodeSpacing, label: agent, type: layerData.type });
                });
            });
            const g = svg.append("g").selectAll("g").data(nodes).join("g").attr("transform", d => `translate(${d.x},${d.y})`);
            g.append("circle").attr("r", 10).attr("fill", "#1e293b")
              .attr("stroke", d => d.type === 'transformer' ? '#ef4444' : d.type === 'mamba' ? '#10b981' : d.type === 'supervisor' ? '#f59e0b' : '#3b82f6')
              .attr("stroke-width", 2).attr("class", "node-circle");
            g.append("text").attr("y", 22).attr("text-anchor", "middle").attr("fill", "#94a3b8").style("font-size", "9px").text(d => d.label);
            window.pulseNN = function() {
                svg.selectAll(".node-circle").transition().duration(200).attr("fill", "#8b5cf6")
                  .transition().duration(600).attr("fill", "#1e293b");
            };
        }


        setTimeout(initD3, 100);

        function wireDropzone(dzId, inputId, kind) {
            const dz = document.getElementById(dzId);
            const input = document.getElementById(inputId);
            ["dragenter","dragover"].forEach(ev => dz.addEventListener(ev, e => {
                e.preventDefault(); dz.classList.add("dragover");
            }));
            ["dragleave","drop"].forEach(ev => dz.addEventListener(ev, e => {
                e.preventDefault(); dz.classList.remove("dragover");
            }));
            dz.addEventListener("drop", e => {
                if (e.dataTransfer.files?.length) uploadFiles(kind, e.dataTransfer.files);
            });
            input.addEventListener("change", () => {
                if (input.files?.length) uploadFiles(kind, input.files);
            });
        }
        wireDropzone("dz-code", "file-code", "code");
        wireDropzone("dz-notes", "file-notes", "notes");

        async function uploadFiles(kind, fileList) {
            const fd = new FormData();
            fd.append("kind", kind);
            Array.from(fileList).forEach(f => fd.append("files", f));
            const res = await fetch("/api/upload", { method: "POST", body: fd });
            const data = await res.json();
            if (!res.ok) { alert(data.detail || "Upload failed"); return; }
            if (kind === "code") {
                uploadedCodePaths = uploadedCodePaths.concat(data.paths);
                document.getElementById("code-uploads").innerText = "Uploaded: " + uploadedCodePaths.map(p => p.split("/").pop()).join(", ");
            } else {
                uploadedNotesPaths = uploadedNotesPaths.concat(data.paths);
                document.getElementById("notes-uploads").innerText = "Uploaded: " + uploadedNotesPaths.map(p => p.split("/").pop()).join(", ");
            }
        }

        function parseDraftSections(text) {
            const parts = text.split(/^(?=##\\s+)/m).filter(Boolean);
            if (!parts.length && text.trim()) return [{ title: "Draft", body: text }];
            return parts.map((p, i) => {
                const lines = p.trim().split('\n');
                const title = (lines[0] || "").replace(/^#+\\s*/, "") || ("Section " + (i+1));
                return { title, body: p };
            });
        }

        function refreshDraftPreview() {
            const text = document.getElementById("draft_text").value || "";
            draftSections = parseDraftSections(text);
            const chips = document.getElementById("draft-section-chips");
            chips.innerHTML = "";
            draftSections.forEach((s, i) => {
                const el = document.createElement("span");
                el.className = "chip" + (i === selectedDraftSection ? " active" : "");
                el.innerText = s.title.slice(0, 40);
                el.onclick = () => { selectedDraftSection = i; refreshDraftPreview(); };
                chips.appendChild(el);
            });
            const cur = draftSections[selectedDraftSection] || draftSections[0];
            document.getElementById("draft-section-view").innerText = cur ? cur.body.slice(0, 1200) : "—";
            document.getElementById("draft-continue-hint").innerText =
                "Sections detected: " + draftSections.length + ". Writer appends continuation after the full draft.";
        }

        async function startPipeline() {
            const topic = document.getElementById("topic").value;
            const code = document.getElementById("code").value.trim();
            const notes = document.getElementById("notes").value.trim();
            const github = document.getElementById("github_url").value.trim();
            const job_mode = document.getElementById("job_mode").value;
            const writer_mode = document.getElementById("writer_mode").value;
            const draft_text = document.getElementById("draft_text").value;
            const sel = document.getElementById("writer_agents");
            const selected_writers = Array.from(sel.selectedOptions).map(o => o.value);

            if (job_mode === "complete_draft" && !draft_text.trim()) {
                alert("Paste your half-written paper for Complete Draft mode.");
                return;
            }

            const codePaths = uploadedCodePaths.slice();
            if (code) codePaths.push(code);
            const notesPaths = uploadedNotesPaths.slice();
            if (notes) notesPaths.push(notes);

            const body = {
                raw_topic: topic,
                raw_code_paths: codePaths,
                raw_notes_paths: notesPaths,
                github_url: github || null,
                job_mode,
                writer_mode,
                selected_writers,
                draft_text: draft_text || "",
            };

            const res = await fetch("/api/jobs", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify(body)
            });
            const data = await res.json();
            if (!res.ok) {
                alert(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail) || "Job failed");
                return;
            }
            currentJobId = data.job_id;
            document.getElementById("log-box").innerHTML +=
                `<div class="log-entry"><span class="badge badge-info">SYSTEM</span> Started ${data.job_id} mode=${data.job_mode} writer=${data.writer_mode}</div>`;
            if (pollTimer) clearInterval(pollTimer);
            pollJob();
            pollTimer = setInterval(pollJob, 2500);
        }

        function onModeChange() {
            const mode = document.getElementById("job_mode").value;
            const draftBox = document.getElementById("draft-box");
            const writerControls = document.getElementById("writer-controls");
            draftBox.style.display = mode === "complete_draft" ? "block" : "none";
            writerControls.style.display = mode === "research_only" ? "none" : "block";
            if (mode === "literature_review") {
                document.getElementById("writer_mode").value = "single";
                const sel = document.getElementById("writer_agents");
                Array.from(sel.options).forEach(o => { o.selected = (o.value === "Literature Review"); });
            }
            if (mode === "complete_draft") {
                document.getElementById("writer_mode").value = "single";
                refreshDraftPreview();
            }
            if (mode === "full_paper") {
                document.getElementById("writer_mode").value = "multi";
            }
            onWriterModeChange();
        }

        function onWriterModeChange() {
            const wm = document.getElementById("writer_mode").value;
            const label = document.getElementById("writer-agent-label");
            if (wm === "single") label.innerText = "Choose one writer agent";
            else label.innerText = "Select writer agent(s) — empty = all sections";
        }

        setTimeout(() => { onModeChange(); loadJobHistory(); }, 50);

        function fmtEta(sec) {
            if (sec === null || sec === undefined) return "—";
            if (sec <= 0) return "done";
            if (sec < 60) return Math.round(sec) + "s";
            return Math.round(sec/60) + "m";
        }

        async function pollJob() {
            if (!currentJobId) return;
            const res = await fetch("/api/jobs/" + currentJobId);
            if (!res.ok) return;
            const data = await res.json();

            const fmt = (v) => (v === null || v === undefined) ? "—" : (v + "%");
            document.getElementById("m-plagiarism").innerText = fmt(data.plagiarism_pct);
            document.getElementById("m-ai").innerText = fmt(data.ai_pct);
            document.getElementById("m-accuracy").innerText = fmt(data.upskill_score);
            document.getElementById("m-status").innerText = data.stage || "—";
            document.getElementById("m-agent").innerText = data.current_agent || "—";
            document.getElementById("m-eta").innerText = fmtEta(data.eta_seconds);
            document.getElementById("m-stage-detail").innerText = data.stage || "—";
            const pct = data.progress_pct || 0;
            document.getElementById("m-progress").style.width = pct + "%";
            document.getElementById("m-progress-label").innerText = pct + "%";
            if (data.manuscript_preview) {
                document.getElementById("manuscript-preview").innerText = data.manuscript_preview;
            }
            if (data.stage === "COMPLETED" || data.stage === "FAILED") {
                loadJobHistory();
            }
        }

        async function loadManuscriptPreview() {
            if (!currentJobId) return;
            const res = await fetch("/api/jobs/" + currentJobId + "/manuscript");
            const data = await res.json();
            document.getElementById("manuscript-preview").innerText = data.markdown || "(empty)";
        }

        async function loadJobHistory() {
            const res = await fetch("/api/jobs");
            const data = await res.json();
            const box = document.getElementById("job-history");
            box.innerHTML = "";
            (data.jobs || []).forEach(j => {
                const div = document.createElement("div");
                div.className = "history-item";
                const left = document.createElement("div");
                left.innerHTML = `<b>${j.job_id}</b><br/><span style="color:var(--text-dim)">${(j.raw_topic||"").slice(0,48)}</span><br/><span style="color:var(--text-dim)">${j.job_mode||""} · ${j.stage||""}</span>`;
                const right = document.createElement("div");
                right.style.display = "flex";
                right.style.gap = "4px";
                const openBtn = document.createElement("button");
                openBtn.innerText = "Open";
                openBtn.onclick = () => { currentJobId = j.job_id; pollJob(); loadManuscriptPreview(); };
                const pdfBtn = document.createElement("button");
                pdfBtn.innerText = "PDF";
                pdfBtn.style.background = "#2563eb";
                pdfBtn.onclick = () => window.open("/download/pdf/" + j.job_id, "_blank");
                const pptBtn = document.createElement("button");
                pptBtn.innerText = "PPTX";
                pptBtn.style.background = "#d97706";
                pptBtn.onclick = () => window.open("/download/pptx/" + j.job_id, "_blank");
                right.appendChild(openBtn); right.appendChild(pdfBtn); right.appendChild(pptBtn);
                div.appendChild(left); div.appendChild(right);
                box.appendChild(div);
            });
            if (!(data.jobs || []).length) box.innerText = "No jobs yet.";
        }

        const ws = new WebSocket("ws://" + window.location.host + "/ws");
        ws.onmessage = function(event) {
            const l = JSON.parse(event.data);
            const logBox = document.getElementById("log-box");
            const badgeClass = l.level === "WARN" ? "badge-warn" : "badge-info";
            logBox.innerHTML += `<div class="log-entry"><span class="badge ${badgeClass}">${l.agent}</span> ${l.content}</div>`;
            logBox.scrollTop = logBox.scrollHeight;
            if (l.agent) document.getElementById("m-agent").innerText = l.agent;
            if (window.pulseNN) window.pulseNN();
        };

        function downloadPDF() {
            if (!currentJobId) return alert("No job selected");
            window.open("/download/pdf/" + currentJobId, "_blank");
        }
        function downloadPPTX() {
            if (!currentJobId) return alert("No job selected");
            window.open("/download/pptx/" + currentJobId, "_blank");
        }
    </script>
</body>
</html>"""
