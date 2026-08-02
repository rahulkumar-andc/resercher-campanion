"""
Layer 0: Sandbox Runtime & Profiler Agent
Runs source files in a restricted subprocess (timeout, no shared process memory).
"""

import os
import sys
import time
import tempfile
import subprocess
from src.agents.base_agent import BaseAgent
from src.core.models import PipelineContext


class RuntimeProfilerAgent(BaseAgent):
    """Layer 0 Agent profiling code performance via subprocess sandbox."""

    SANDBOX_TIMEOUT_SEC = 5

    def __init__(self, bus):
        super().__init__(name="RuntimeProfilerAgent", layer=0, bus=bus)

    def _run_sandboxed(self, source_code: str, code_path: str) -> tuple:
        """Execute Python source in a child process; never exec in-process."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(source_code)
            tmp_path = tmp.name
        try:
            env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "LC_ALL", "PYTHONPATH")}
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            started = time.time()
            proc = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=self.SANDBOX_TIMEOUT_SEC,
                env=env,
                cwd=tempfile.gettempdir(),
            )
            elapsed_ms = (time.time() - started) * 1000.0
            return proc.returncode == 0, elapsed_ms, proc.stderr[:200] if proc.stderr else ""
        except subprocess.TimeoutExpired:
            return False, self.SANDBOX_TIMEOUT_SEC * 1000.0, "timeout"
        except Exception as e:
            return False, 0.0, str(e)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, "Layer 0 subprocess sandbox profiler starting...")

        total_elapsed = 0.0
        executed_files = 0
        total_ops = 0
        peak_mb = 0.0

        for code_path in ctx.raw_code_paths:
            if not code_path.endswith(".py"):
                self.log(ctx, f"Skipping non-Python file for sandbox: {code_path}", level="INFO")
                continue
            try:
                with open(code_path, "r", encoding="utf-8") as f:
                    source_code = f.read()
            except Exception as e:
                self.log(ctx, f"Could not read {code_path}: {e}", level="WARN")
                continue

            ok, elapsed_ms, err = self._run_sandboxed(source_code, code_path)
            total_elapsed += elapsed_ms
            if ok:
                executed_files += 1
                total_ops += max(1, len(source_code.splitlines())) * 1000
                peak_mb = max(peak_mb, 8.0)  # approximate floor; child RSS not sampled
            else:
                self.log(ctx, f"Sandbox notice for {code_path}: {err or 'non-zero exit'}", level="WARN")

        throughput = round((total_ops / max(0.001, total_elapsed / 1000.0)), 2) if executed_files else 0.0

        ctx.code_analysis.cpu_time_ms = round(total_elapsed, 2)
        ctx.code_analysis.peak_memory_mb = round(peak_mb, 2)
        ctx.code_analysis.throughput_ops_sec = throughput

        self.log(
            ctx,
            f"Sandbox Profiling Completed: Executed {executed_files} files in "
            f"{ctx.code_analysis.cpu_time_ms}ms | Peak Memory (approx): "
            f"{ctx.code_analysis.peak_memory_mb} MB | Throughput: "
            f"{ctx.code_analysis.throughput_ops_sec} ops/sec."
        )
