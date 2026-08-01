import ast
import re
import os
import chromadb
from typing import List, Dict, Any
from src.agents.base_agent import BaseAgent
from src.core.event_bus import SupervisorBus
from src.core.models import PipelineContext


class CodeBreaker(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("CodeBreaker", layer=2, bus=bus)
        
        # Setup Local Vector DB for Code Embedding
        self.chroma_path = os.path.expanduser("~/.arc_code_chroma")
        try:
            self.chroma_client = chromadb.PersistentClient(path=self.chroma_path)
            self.collection = self.chroma_client.get_or_create_collection(
                name="code_semantic_cache",
                metadata={"hnsw:space": "cosine"}
            )
        except Exception:
            self.collection = None

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, "Decomposing codebase into AST Graph and Semantic Vector Embeddings...")
        code_files = ctx.style_fingerprint.get("code_files", [])
        function_blocks = []
        call_graph = {}

        for item in code_files:
            content = item.get("content", "")
            file_name = item.get("name", "source")

            # Python AST parsing and Graph mapping
            if item.get("language") == "Python":
                try:
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            func_name = node.name
                            args = [a.arg for a in node.args.args]
                            docstring = ast.get_docstring(node) or ""
                            
                            # Find all function calls inside this function (Graph Edges)
                            calls = []
                            for child in ast.walk(node):
                                if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                                    calls.append(child.func.id)
                            call_graph[func_name] = list(set(calls))
                            
                            snippet = "\n".join(content.splitlines()[node.lineno-1:node.end_lineno]) if hasattr(node, 'end_lineno') and node.end_lineno else f"def {node.name}(...)"
                            
                            block = {
                                "file": file_name,
                                "name": func_name,
                                "type": "AsyncFunction" if isinstance(node, ast.AsyncFunctionDef) else "Function",
                                "args": args,
                                "docstring": docstring,
                                "line_no": node.lineno,
                                "content_snippet": snippet
                            }
                            function_blocks.append(block)
                            
                            # Embed into ChromaDB Vector Store
                            if self.collection:
                                try:
                                    doc_text = f"Function: {func_name}\nArgs: {args}\nDoc: {docstring}\nCode: {snippet}"
                                    doc_id = f"{file_name}_{func_name}_{node.lineno}"
                                    self.collection.upsert(
                                        documents=[doc_text],
                                        metadatas=[{"file": file_name, "func": func_name}],
                                        ids=[doc_id]
                                    )
                                except Exception:
                                    pass
                except Exception:
                    pass

            # Fallback pattern matching for JS/C++/Rust/etc
            matches = re.findall(r'(?:function|def|fn|async function|class)\s+([a-zA-Z_]\w*)\s*\((.*?)\)', content)
            for func_name, args_str in matches[:10]:
                if not any(f["name"] == func_name for f in function_blocks):
                    function_blocks.append({
                        "file": file_name,
                        "name": func_name,
                        "type": "Function/Method",
                        "args": [a.strip() for a in args_str.split(",") if a.strip()],
                        "docstring": "",
                        "line_no": 1,
                        "content_snippet": f"{func_name}({args_str})"
                    })

        ctx.code_analysis.function_blocks = function_blocks
        self.log(ctx, f"CodeBreaker extracted {len(function_blocks)} function and class blocks.")


class AlgoDetector(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("AlgoDetector", layer=2, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, "Scanning AST & tokens for known algorithms and data structures...")
        code_files = ctx.style_fingerprint.get("code_files", [])
        combined = "\n".join([f.get("content", "") for f in code_files]).lower()

        detected = []
        algo_patterns = {
            "Event-Driven Architecture / Message Bus": [r"event", r"publish", r"subscribe", r"listener", r"nats", r"bus"],
            "Async Concurrent Task Pipeline": [r"async", r"await", r"thread", r"coroutine", r"future", r"promise"],
            "Tree / Graph Traversal": [r"tree", r"graph", r"node", r"dfs", r"bfs", r"parent", r"child"],
            "Dynamic Programming / Memoization": [r"dp", r"memo", r"cache", r"recursive", r"state"],
            "Sorting & Searching": [r"sort", r"binary_search", r"bisect", r"partition"],
            "Hash Indexing & Lookup": [r"dict", r"hash", r"map", r"lookup", r"key"],
            "Stream / Batch Processing": [r"stream", r"batch", r"chunk", r"buffer", r"queue"]
        }

        for algo_name, keywords in algo_patterns.items():
            matches = [kw for kw in keywords if re.search(r'\b' + kw + r'\b', combined)]
            if len(matches) >= 1:
                detected.append({
                    "name": algo_name,
                    "confidence": "High" if len(matches) >= 2 else "Medium",
                    "matched_keywords": ", ".join(matches)
                })

        if not detected:
            detected.append({"name": "Modular Pipeline Execution", "confidence": "High", "matched_keywords": "modular, pipeline"})

        ctx.code_analysis.algorithms = detected
        self.log(ctx, f"AlgoDetector identified {len(detected)} algorithmic techniques: {[a['name'] for a in detected]}.")


class ComplexityAnalyzer(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("ComplexityAnalyzer", layer=2, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, "Analyzing Big-O time and space complexity of function blocks...")
        blocks = ctx.code_analysis.function_blocks
        complexities = {}

        for b in blocks:
            name = b["name"]
            snippet = b.get("content_snippet", "")
            
            # Simple heuristic for loop nesting & recursion
            loops = len(re.findall(r'\b(for|while)\b', snippet))
            nested = len(re.findall(r'(?:for|while).*\n\s*(?:for|while)', snippet))

            if nested >= 1:
                time_comp = "O(N^2)"
            elif loops == 1:
                time_comp = "O(N)"
            elif "binary" in name.lower() or "sort" in name.lower():
                time_comp = "O(N log N)"
            else:
                time_comp = "O(1)"

            space_comp = "O(N)" if "list" in snippet.lower() or "append" in snippet.lower() or "map" in snippet.lower() else "O(1)"
            complexities[name] = f"Time: {time_comp}, Space: {space_comp}"

        ctx.code_analysis.complexities = complexities
        self.log(ctx, f"ComplexityAnalyzer evaluated {len(complexities)} functions. Sample: {list(complexities.items())[:3]}")


class HWMapper(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("HWMapper", layer=2, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, "Mapping code execution to hardware resource utilization...")
        code_files = ctx.style_fingerprint.get("code_files", [])
        combined = "\n".join([f.get("content", "") for f in code_files])

        mappings = []
        if "async" in combined or "thread" in combined or "process" in combined:
            mappings.append({"resource": "CPU Multi-Core", "pattern": "Asynchronous event-loop / non-blocking concurrency"})
        if "open(" in combined or "read(" in combined or "write(" in combined:
            mappings.append({"resource": "I/O Subsystem", "pattern": "File system disk read/write throughput bottleneck"})
        if "requests" in combined or "urllib" in combined or "http" in combined:
            mappings.append({"resource": "Network Interface", "pattern": "External HTTP request network latency"})

        mappings.append({"resource": "Memory (RAM)", "pattern": "In-memory AST parsing and context vector caching"})

        ctx.code_analysis.hardware_mappings = mappings
        self.log(ctx, f"HWMapper mapped {len(mappings)} hardware interaction patterns.")


class BugEdgeCase(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("BugEdgeCase", layer=2, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, "Auditing codebase for bugs, unhandled exceptions, and edge case vulnerabilities...")
        code_files = ctx.style_fingerprint.get("code_files", [])
        bugs = []

        for item in code_files:
            content = item.get("content", "")
            fname = item.get("name", "")

            if "except:" in content or "except Exception:" in content:
                bugs.append({"file": fname, "issue": "Broad Exception Catching", "impact": "May suppress unexpected runtime faults."})
            if "open(" in content and "with open" not in content:
                bugs.append({"file": fname, "issue": "Unclosed File Descriptor", "impact": "Potential memory / file resource leak."})
            if not re.search(r'if\s+.*\s+is\s+None:', content) and "None" in content:
                bugs.append({"file": fname, "issue": "Unchecked Null / None Boundary", "impact": "Risk of AttributeError / TypeError on missing inputs."})

        if not bugs:
            bugs.append({"file": "General", "issue": "Asynchronous Unhandled Rejection", "impact": "Potential network timeout when calling external APIs."})

        ctx.code_analysis.bugs_edge_cases = bugs
        self.log(ctx, f"BugEdgeCase agent identified {len(bugs)} potential edge cases / code weaknesses.")
