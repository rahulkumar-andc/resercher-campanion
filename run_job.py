import os
import time
from src.core.models import PipelineContext
from src.agents.layer6_supervisor import SupervisorAgent

def run():
    job_id = f"job_ic_tester_{int(time.time())}"
    topic = "Automated Hardware Testing with Elite IC Tester"
    repo_url = "https://github.com/rahulkumar-andc/elite-ic-tester"
    
    ctx = PipelineContext(
        job_id=job_id,
        raw_topic=topic,
        raw_code_paths=[repo_url],
        raw_notes_paths=[]
    )
    
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Starting job {job_id} for {repo_url}...")
    
    supervisor = SupervisorAgent()
    
    def log_handler(msg):
        print(f"[{msg.layer}] {msg.agent_name}: {msg.content}")
        
    supervisor.bus.subscribe(log_handler)
    
    supervisor.execute_pipeline(ctx, output_dir=output_dir)
    print(f"Job {job_id} completed!")

if __name__ == "__main__":
    run()
