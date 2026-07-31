#!/usr/bin/env python3
import os
import sys
import argparse
import time
from src.core.models import PipelineContext
from src.agents.layer6_supervisor import SupervisorAgent


def print_banner():
    banner = """
  ┌─────────────────────────────────────────────────────────────┐
  │         AUTONOMOUS RESEARCH COMPANION (RC-SYSTEM)           │
  │     6-Layer Multi-Agent Architecture Engine (Layer 1-6)    │
  └─────────────────────────────────────────────────────────────┘
"""
    print(banner)


def main():
    print_banner()
    parser = argparse.ArgumentParser(description="Autonomous Research Companion Multi-Agent Pipeline CLI")
    parser.add_argument("--topic", type=str, default="Autonomous Multi-Agent Systems & Code Complexity Analysis", help="Research Topic")
    parser.add_argument("--code", type=str, default="./sample_data/sample_code.py", help="Path to raw source code file or directory")
    parser.add_argument("--notes", type=str, default="./sample_data/sample_notes.txt", help="Path to user notes / PDF file")
    parser.add_argument("--out", type=str, default="./output", help="Output directory for ResearchPaper.pdf & Presentation.pptx")
    parser.add_argument("--web", action="store_true", help="Launch FastAPI Web Dashboard UI")
    parser.add_argument("--port", type=int, default=8000, help="Web server port (default: 8000)")

    args = parser.parse_args()

    if args.web:
        print(f"🚀 Starting Research Companion Web Dashboard on http://localhost:{args.port}...")
        import uvicorn
        from src.web.app import app
        uvicorn.run(app, host="0.0.0.0", port=args.port)
        return

    job_id = f"job_{int(time.time())}"
    print(f"📋 Job ID: {job_id}")
    print(f"📌 Research Topic: {args.topic}")
    print(f"📁 Source Code Path: {args.code}")
    print(f"📝 Notes Path: {args.notes}")
    print(f"🎯 Output Directory: {args.out}\n")

    ctx = PipelineContext(
        job_id=job_id,
        raw_topic=args.topic,
        raw_code_paths=[args.code] if os.path.exists(args.code) else [],
        raw_notes_paths=[args.notes] if os.path.exists(args.notes) else []
    )

    supervisor = SupervisorAgent()

    # Terminal progress logger
    def terminal_logger(msg):
        layer_str = f"[L{msg.layer}]" if msg.layer else "[SYS]"
        color_prefix = "\033[95m" if msg.level == "STAGE" else ("\033[92m" if msg.level == "INFO" else "\033[91m")
        reset_color = "\033[0m"
        print(f"{color_prefix}{layer_str} {msg.agent_name:<18} | {msg.content}{reset_color}")

    supervisor.bus.subscribe(terminal_logger)

    print("▶ Executing Multi-Agent Pipeline Across Layers 1 to 5...")
    start_t = time.time()
    ctx = supervisor.execute_pipeline(ctx, output_dir=args.out)
    elapsed = time.time() - start_t

    print("\n" + "="*60)
    if ctx.stage.value == "COMPLETED":
        print(f"✅ PIPELINE SUCCESSFULLY COMPLETED in {elapsed:.2f} seconds!")
        print(f"📄 Research Paper PDF: {ctx.output.pdf_path}")
        print(f"📊 Presentation Deck: {ctx.output.pptx_path}")
        print(f"⭐ Critic Quality Score: {ctx.synthesis.critic_score}/100")
    else:
        print(f"❌ PIPELINE FAILED: {ctx.errors}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
