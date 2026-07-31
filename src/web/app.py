import os
import time
import asyncio
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
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


@app.get("/")
def read_root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


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
    code_files: List[UploadFile] = File(None),
    notes_files: List[UploadFile] = File(None)
):
    job_id = f"job_{int(time.time())}"
    saved_code_paths = []
    saved_notes_paths = []

    if code_files:
        for f in code_files:
            if f.filename:
                path = os.path.join(UPLOAD_DIR, f"{job_id}_{f.filename}")
                with open(path, "wb") as buffer:
                    buffer.write(await f.read())
                saved_code_paths.append(path)

    if notes_files:
        for f in notes_files:
            if f.filename:
                path = os.path.join(UPLOAD_DIR, f"{job_id}_{f.filename}")
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

    def process_job():
        supervisor = SupervisorAgent()
        supervisor.bus.subscribe_async(broadcast_log)
        supervisor.execute_pipeline(ctx, output_dir=OUTPUT_DIR)

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


@app.get("/api/download/pdf")
def download_pdf():
    pdf_path = os.path.join(OUTPUT_DIR, "ResearchPaper.pdf")
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, media_type="application/pdf", filename="ResearchPaper.pdf")
    return JSONResponse({"error": "PDF not yet generated"}, status_code=404)


@app.get("/api/download/pptx")
def download_pptx():
    pptx_path = os.path.join(OUTPUT_DIR, "Presentation.pptx")
    if os.path.exists(pptx_path):
        return FileResponse(pptx_path, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", filename="Presentation.pptx")
    return JSONResponse({"error": "PPTX not yet generated"}, status_code=404)
