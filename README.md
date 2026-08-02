# 🔬 Autonomous Research Companion (ARC)

> **Ethical & Defensive Research Automation Framework**  
> *Transforming raw codebases and notes into structured, highly dense academic research papers, presentation decks, and BibTeX citations.*

---

## 📌 Safety & Responsible Use Banner

> [!IMPORTANT]
> **Defensive Security & Research Scope Statement**  
> This system is designed exclusively for ethical bug bounty hunting, defensive software engineering research, automated documentation, and academic analysis.  
> - **Dense Fact-Driven Analytics**: Exclusively leverages LLMs to produce concise, factual reports devoid of generic fluff.
> - **Dry-Run Mode**: Supports offline fallback execution.
> - **Zero Vulnerability Exploitation**: Analyzes code weaknesses solely for defensive remediation and academic grounding.

---

## 🏗️ 6-Layer Multi-Agent Architecture (LangGraph Powered)

Powered by **LangGraph** and a persistent **SQLite Checkpointer**, ARC coordinates a highly resilient 6-layer agent mesh:

```mermaid
flowchart TD
    %% Define Styles
    classDef supervisor fill:#8e44ad,stroke:#5b2c6f,color:white,stroke-width:4px;
    classDef l1 fill:#3498db,stroke:#2980b9,color:white;
    classDef l2 fill:#e74c3c,stroke:#c0392b,color:white;
    classDef l3 fill:#2ecc71,stroke:#27ae60,color:white;
    classDef l4 fill:#f39c12,stroke:#d68910,color:white;
    classDef l45 fill:#d35400,stroke:#a04000,color:white;
    classDef l5 fill:#34495e,stroke:#2c3e50,color:white;
    classDef io fill:#95a5a6,stroke:#7f8c8d,color:black,stroke-dasharray: 5 5;
    
    %% Inputs (User Data)
    subgraph IODisks [User Input Sources]
        direction LR
        RawCode[(Raw Source Code)]:::io
        RawNotes[(PDFs & User Notes)]:::io
        RawTopic[(Topic String)]:::io
    end
    
    %% Central Hub / Brain (Event Bus)
    Sup((Layer 6: LangGraph Supervisor)):::supervisor

    %% LAYER 1: INPUT & PARSING
    subgraph Layer1 [Layer 1: Input & Parsing]
        direction LR
        GI(Git Ingestor):::l1
        CI(Code Ingestor):::l1
        DI(Data Ingestor):::l1
        SA(Style Agent):::l1
        QP(Query Parser):::l1
    end
    
    %% LAYER 2: CODE ANALYSIS
    subgraph Layer2 [Layer 2: Code Analysis]
        direction LR
        CB(Code Breaker):::l2
        AD(Algo Detector):::l2
        CA(Complexity Analyzer):::l2
        HM(HW Mapper):::l2
        BE(Bug & Edge Case):::l2
    end
    
    %% LAYER 3: RESEARCH & GROUNDING
    subgraph Layer3 [Layer 3: Research & Grounding]
        direction LR
        WSA(Web Search):::l3
        AA(ArXiv Agent):::l3
        CSA(CS Agent):::l3
        EA(Electronics Agent):::l3
        LA(Literature Agent):::l3
        GF(Gap Finder):::l3
    end
    
    %% LAYER 4: SYNTHESIS & STRUCTURE
    subgraph Layer4 [Layer 4: Synthesis & Structure]
        direction LR
        Conn(Connector):::l4
        OB(Outline Builder):::l4
        Cit(Citation Agent):::l4
        Crit(Critic Agent):::l4
    end

    %% LAYER 4.5: QUALITY AUDIT & PEER REVIEW
    subgraph Layer45 [Layer 4.5: Quality Audit & Peer Review]
        direction LR
        PC(Plagiarism Checker):::l45
        PR(Plagiarism Remediator):::l45
        AI(AI Percentage Auditor):::l45
        PRV(Peer Reviewer Agent):::l45
        FQA(Format Quality Auditor):::l45
    end
    
    %% LAYER 5: OUTPUT GENERATION
    subgraph Layer5 [Layer 5: Local LLM Output]
        direction LR
        WA(Writer Agent - Ollama):::l5
        PDF(PDF Exporter):::l5
        PPT(PPT Exporter):::l5
    end
    
    %% Outputs (Deliverables)
    subgraph Deliverables [Final Export]
        direction LR
        OutPDF[(ResearchPaper.pdf)]:::io
        OutPPT[(Presentation.pptx)]:::io
        OutBIB[(References.bib)]:::io
    end

    %% --- FULLY CONNECTED WIRES & DATA FLOW ---

    %% 1. Input Source Wires -> Layer 1 Agents
    RawCode -->|"Raw Files"| CI
    RawNotes -->|"Text & Metadata"| DI
    RawNotes -->|"Style Samples"| SA
    RawTopic -->|"Topic String"| QP

    %% 2. Layer 1 -> Layer 2 & 3 Wires
    CI -->|"AST Trees & Tokens"| CB & AD & CA & HM & BE
    DI -->|"Parsed JSON Notes"| LA
    QP -->|"Sub-queries"| AA & CSA & EA
    SA -->|"Style Fingerprint"| WA

    %% 3. Layer 2 Code Analysis Wires -> Layer 3 & 4
    CB -->|"Function Blocks"| AA
    AD -->|"Algorithm Types"| CSA
    CA -->|"Big-O Metrics"| Conn
    HM -->|"Hardware Specs"| EA
    BE -->|"Code Weaknesses"| GF

    %% 4. Layer 3 Research Wires -> Layer 4 Synthesis
    AA -->|"BibTeX & Papers"| Cit & Conn
    CSA -->|"CS Benchmarks"| Conn
    EA -->|"Circuit Specs"| Conn
    LA -->|"Background Knowledge"| Conn
    GF -->|"Identified Research Gaps"| OB

    %% 5. Layer 4 Synthesis Wires -> Layer 5 Writer
    Conn -->|"Unified Context"| WA
    OB -->|"Section Outlines"| WA
    Cit -->|"IEEE/ACM References"| WA
    WA <-->|"Draft Review & Feedback"| Crit

    %% 6. Layer 5 Writer -> Layer 4.5 Quality Audit Wires
    WA -->|"Draft Manuscript"| PC & AI & PRV & FQA

    %% 7. Layer 4.5 Self-Healing Feedback Loop Wires
    PC -.->|"Similarity > 15%"| PR
    AI -.->|"AI Score > 10%"| PR
    PR -.->|"Re-synthesized Text"| WA
    PRV -.->|"Reviewer Questions"| OB
    FQA -.->|"Grammar Fixes"| WA

    %% 8. Approved QA -> Exporters & Deliverables
    PC & AI & PRV & FQA -->|"Quality Approved"| PDF & PPT & Cit
    PDF -->|"Rendered PDF"| OutPDF
    PPT -->|"Rendered Deck"| OutPPT
    Cit -->|"BibTeX Export"| OutBIB

    %% 9. Layer 6 Supervisor Event Bus Monitoring (All Agents)
    Sup <.-> GI & CI & DI & SA & QP
    Sup <.-> CB & AD & CA & HM & BE
    Sup <.-> WSA & AA & CSA & EA & LA & GF
    Sup <.-> Conn & OB & Cit & Crit
    Sup <.-> PC & PR & AI & PRV & FQA
    Sup <.-> WA & PDF & PPT
```

---

## 🌟 Key Features & Recent Upgrades

1. **Ollama Local LLM Integration**: Generates deep, factual analytical reports locally using models like `llama3.1` or `qwen2.5-coder`. Automatically injects detected novelty gaps and algorithm complexities directly into the LLM synthesis prompt.
2. **Persistent Checkpointing**: Utilizes `langgraph.checkpoint.sqlite.SqliteSaver` to persist multi-agent job states safely to `checkpoints.sqlite`, preventing data loss during complex research execution.
3. **Real-time Telemetry WebSocket**: Live backend logs stream directly into a front-end "Hacker-Style" terminal UI while the agents work.
4. **Interactive Dashboards**:
   - `/`: Main interactive launcher and hacker terminal.
   - `/nn`: Live 3D Force-Graph visualization of agent topologies.
   - `/nn2d`: Interactive 2D Network graph of the agent state space.
   - `/vault`: A persistent Artifacts Vault for browsing and downloading generated PDFs and PPTXs.

### QA limitations

ARC's QA values are local heuristic estimates, not externally validated scores. The corpus-overlap value compares n-grams against context already provided to the pipeline; it is not a plagiarism-database result. The AI-style value uses local buzzword and passive-voice signals; it is not an AI-authorship determination. Fact checking only compares selected statistics with collected context text and does not verify claims. Use independent plagiarism, authorship, and fact-verification services for publication or compliance decisions.

---

## 📦 Project Directory Structure

```
reserch-campanion/
├── main.py                    # FastAPI Web Server Launcher
├── run_cli.py                 # Direct CLI Execution Engine
├── checkpoints.sqlite         # Persistent LangGraph Job States
├── src/                       # Core Source Code
│   ├── agents/                # 6-Layer Multi-Agent Classes
│   │   ├── layer1_input.py
│   │   ├── layer2_code.py
│   │   ├── layer3_research.py
│   │   ├── layer4_synthesis.py
│   │   ├── layer5_output.py   # Ollama LLM Synthesis integration
│   │   └── layer6_supervisor.py # LangGraph Orchestrator
│   ├── core/                  
│   │   ├── llm_client.py      # Ollama Interoperability (300s timeout logic)
│   │   └── event_bus.py       # Live WebSocket Event Emitter
│   ├── exporters/             # Document Exporters (ReportLab & PPTX)
│   └── web/                   # FastAPI Web UI Backend
│       ├── app.py             
│       └── static/            
│           ├── index.html     # Main Launcher UI
│           ├── vault.html     # Artifacts Vault
│           ├── nn.html        # 3D Agent Topology
│           └── nn_2d.html     # 2D Agent Topology
└── output/                    # Generated Deliverables
    ├── ResearchPaper.pdf
    ├── ResearchPaper.md
    └── Presentation.pptx
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites & Installation

You must have [Ollama](https://ollama.com/) running locally with at least one compatible model (e.g., `ollama run llama3.1`).

```bash
# Clone the repository
cd reserch-campanion

# Install Python dependencies
pip install -r requirements.txt
# Optional: enable local GPT-2 perplexity scoring in HumanizerPipeline
pip install -r requirements-humanizer.txt
```

### 2. Launching Interactive Web Dashboard

Launch the FastAPI backend with real-time WebSocket terminal log streaming:

```bash
python main.py
```

Open your browser at:  
👉 **`http://localhost:8000`**

### 3. Running via Command Line Interface (CLI)

Generate a complete paper and deck silently from the command line:

```bash
python run_cli.py \
  --topic "Distributed Asynchronous Agent Architecture" \
  --code ./sample_data/sample_code.py \
  --notes ./sample_data/sample_notes.txt \
  --output ./output
```

---

## 🛡️ License & Ethical Disclosure

Built as a defensive security research tool. Redistribution or usage must align with ethical software disclosure standards.
