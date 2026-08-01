import os
import time
import argparse
from src.core.models import PipelineContext
from src.agents.layer6_supervisor import SupervisorAgent

def console_logger(msg):
    print(f"[{msg.level}] {msg.agent_name}: {msg.content}")

def main():
    parser = argparse.ArgumentParser(description="Run ARC Pipeline from CLI")
    parser.add_argument("--topic", type=str, default="System Analysis", help="Research topic")
    parser.add_argument("--code", type=str, help="Path to code file or directory")
    parser.add_argument("--notes", type=str, help="Path to notes file or directory")
    args = parser.parse_args()

    job_id = f"cli_{int(time.time())}"
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)

    code_paths = [args.code] if args.code else []
    notes_paths = [args.notes] if args.notes else []

    ctx = PipelineContext(
        job_id=job_id,
        raw_topic=args.topic,
        raw_code_paths=code_paths,
        raw_notes_paths=notes_paths
    )

    print(f"Starting pipeline job: {job_id}")
    
    supervisor = SupervisorAgent()
    
    # We use sync callback for CLI
    def sync_logger(msg):
        console_logger(msg)
        
    supervisor.bus.subscribe_sync(sync_logger)
    
    supervisor.execute_pipeline(ctx, output_dir=output_dir)
    print(f"Pipeline finished! Check {output_dir} for results.")

if __name__ == "__main__":
    main()
