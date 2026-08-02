import os
import time
import asyncio
import threading
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.core.models import PipelineContext
from src.agents.layer6_supervisor import SupervisorAgent

app = FastAPI(title="Autonomous Research Companion Web API", version="1.0.0")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "output")
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

active_jobs: dict = {}
active_websockets: List[WebSocket] = []
JOB_TTL_SECONDS = 60 * 60
supervisor: Optional[SupervisorAgent] = None
supervisor_init_lock = threading.Lock()
supervisor_run_lock = threading.Lock()
app_loop: Optional[asyncio.AbstractEventLoop] = None


def _broadcast_from_supervisor(msg) -> None:
    if app_loop and app_loop.is_running():
        asyncio.run_coroutine_threadsafe(broadcast_log(msg), app_loop)


def _get_supervisor() -> SupervisorAgent:
    global supervisor
    with supervisor_init_lock:
        if supervisor is None:
            supervisor = SupervisorAgent()
            supervisor.bus.subscribe(_broadcast_from_supervisor)
        return supervisor


def _safe_upload_path(job_id: str, filename: str) -> str:
    safe_name = Path(filename.replace("\\", "/")).name
    if safe_name in {"", ".", ".."}:
        raise ValueError("Invalid upload filename")
    return os.path.join(UPLOAD_DIR, f"{job_id}_{safe_name}")


@app.on_event("startup")
async def initialize_supervisor() -> None:
    global app_loop
    app_loop = asyncio.get_running_loop()
    _get_supervisor()


async def _evict_job_after_ttl(job_id: str, ctx: PipelineContext) -> None:
    """Retain completed job status briefly without retaining contexts indefinitely."""
    await asyncio.sleep(JOB_TTL_SECONDS)
    if active_jobs.get(job_id) is ctx:
        active_jobs.pop(job_id, None)


@app.get("/")
def read_root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/nn", response_class=HTMLResponse)
async def serve_nn_ui():
    """Serve the 3D Neural Topology UI"""
    with open(os.path.join(STATIC_DIR, "nn.html")) as f:
        return f.read()

@app.get("/nn2d", response_class=HTMLResponse)
async def serve_nn2d_ui():
    """Serve the original 2D Neural Topology UI"""
    with open(os.path.join(STATIC_DIR, "nn_2d.html")) as f:
        return f.read()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_websockets.remove(websocket)


async def broadcast_log(msg):
    log_data = {
        "agent_name": msg.agent_name,
        "layer": msg.layer,
        "content": msg.content,
        "level": msg.level,
        "timestamp": msg.timestamp
    }
    for ws in list(active_websockets):
        try:
            await ws.send_json(log_data)
        except Exception:
            pass


@app.post("/api/run")
async def run_pipeline_api(
    background_tasks: BackgroundTasks,
    topic: str = Form(...),
    repo_url: Optional[str] = Form(None),
    code_files: List[UploadFile] = File(None),
    notes_files: List[UploadFile] = File(None)
):
    job_id = f"job_{int(time.time())}"
    saved_code_paths = []
    saved_notes_paths = []

    if repo_url:
        saved_code_paths.append(repo_url)

    if code_files:
        for f in code_files:
            if f.filename:
                path = _safe_upload_path(job_id, f.filename)
                with open(path, "wb") as buffer:
                    buffer.write(await f.read())
                saved_code_paths.append(path)

    if notes_files:
        for f in notes_files:
            if f.filename:
                path = _safe_upload_path(job_id, f.filename)
                with open(path, "wb") as buffer:
                    buffer.write(await f.read())
                saved_notes_paths.append(path)

    # Fallback to sample data if no files uploaded
    sample_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "sample_data")
    if not saved_code_paths:
        saved_code_paths.append(os.path.join(sample_dir, "sample_code.py"))
    if not saved_notes_paths:
        saved_notes_paths.append(os.path.join(sample_dir, "sample_notes.txt"))

    ctx = PipelineContext(
        job_id=job_id,
        raw_topic=topic,
        raw_code_paths=saved_code_paths,
        raw_notes_paths=saved_notes_paths
    )

    active_jobs[job_id] = ctx

    loop = asyncio.get_running_loop()
    def process_job():
        try:
            with supervisor_run_lock:
                _get_supervisor().execute_pipeline(ctx, output_dir=OUTPUT_DIR)
        finally:
            asyncio.run_coroutine_threadsafe(_evict_job_after_ttl(job_id, ctx), loop)

    background_tasks.add_task(process_job)

    return JSONResponse({
        "status": "started",
        "job_id": job_id,
        "message": "Autonomous multi-agent pipeline initiated."
    })


@app.get("/api/job/{job_id}")
def get_job_status(job_id: str):
    ctx = active_jobs.get(job_id)
    if not ctx:
        return JSONResponse({"error": "Job not found"}, status_code=404)

    return {
        "job_id": ctx.job_id,
        "topic": ctx.raw_topic,
        "stage": ctx.stage.value,
        "files_analyzed": ctx.code_analysis.file_count,
        "total_lines": ctx.code_analysis.total_lines,
        "critic_score": ctx.synthesis.critic_score,
        "pdf_available": os.path.exists(ctx.output.pdf_path) if ctx.output.pdf_path else False,
        "pptx_available": os.path.exists(ctx.output.pptx_path) if ctx.output.pptx_path else False,
        "errors": ctx.errors
    }


@app.get("/vault", response_class=HTMLResponse)
async def serve_vault_ui():
    """Serve the Artifacts Vault UI"""
    with open(os.path.join(STATIC_DIR, "vault.html")) as f:
        return f.read()

@app.get("/api/vault")
def list_vault_artifacts():
    """List all generated PDFs and PPTXs in the output directory."""
    artifacts = []
    if os.path.exists(OUTPUT_DIR):
        for f in os.listdir(OUTPUT_DIR):
            if f.endswith(".pdf") or f.endswith(".pptx"):
                filepath = os.path.join(OUTPUT_DIR, f)
                stat = os.stat(filepath)
                artifacts.append({
                    "filename": f,
                    "size": stat.st_size,
                    "created_at": stat.st_mtime
                })
    # Sort by newest first
    artifacts.sort(key=lambda x: x["created_at"], reverse=True)
    return {"artifacts": artifacts}

@app.get("/api/download/pdf/{job_id}")
def download_pdf(job_id: str):
    pdf_path = os.path.join(OUTPUT_DIR, f"{job_id}_ResearchPaper.pdf")
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, media_type="application/pdf", filename=f"{job_id}_ResearchPaper.pdf")
    return JSONResponse({"error": "PDF not yet generated"}, status_code=404)


@app.get("/api/download/pptx/{job_id}")
def download_pptx(job_id: str):
    pptx_path = os.path.join(OUTPUT_DIR, f"{job_id}_Presentation.pptx")
    if os.path.exists(pptx_path):
        return FileResponse(pptx_path, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", filename=f"{job_id}_Presentation.pptx")
    return JSONResponse({"error": "PPTX not yet generated"}, status_code=404)

@app.get("/api/download/file/{filename}")
def download_file(filename: str):
    # Used for the Artifact Vault direct downloads
    file_path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(file_path):
        media_type = "application/pdf" if filename.endswith(".pdf") else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        return FileResponse(file_path, media_type=media_type, filename=filename)
    return JSONResponse({"error": "File not found"}, status_code=404)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.web.app:app", host="0.0.0.0", port=8000, reload=True)
