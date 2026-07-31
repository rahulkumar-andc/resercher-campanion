# Autonomous Research Companion — System Architecture

## Overview
The Autonomous Research Companion is a 6-layer multi-agent system designed to transform raw code, unstructured notes/PDFs, and high-level research topics into fully-formatted research papers (PDF) and presentations (PPTX).

---

## Architecture Flowchart

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
    Sup((Layer 6: Supervisor Agent\nCentral Event Bus & Router)):::supervisor

    %% LAYER 1: INPUT & PARSING
    subgraph Layer1 [Layer 1: Input & Parsing]
        direction LR
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
    subgraph Layer5 [Layer 5: Output Generation]
        direction LR
        WA(Writer Agent):::l5
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
    Sup <.-> CI & DI & SA & QP
    Sup <.-> CB & AD & CA & HM & BE
    Sup <.-> AA & CSA & EA & LA & GF
    Sup <.-> Conn & OB & Cit & Crit
    Sup <.-> PC & PR & AI & PRV & FQA
    Sup <.-> WA & PDF & PPT
```

---

## Layer Breakdown

### Layer 6: Central Orchestrator & Router (`SupervisorAgent`)
- Monitors state and routes data between layers asynchronously.

### Layer 1: Input & Parsing (4 Agents)
- **Code Ingestor (`CI`)**, **Data Ingestor (`DI`)**, **Style Agent (`SA`)**, **Query Parser (`QP`)**.

### Layer 2: Code Analysis (5 Agents)
- **Code Breaker (`CB`)**, **Algo Detector (`AD`)**, **Complexity Analyzer (`CA`)**, **HW Mapper (`HM`)**, **Bug & Edge Case (`BE`)**.

### Layer 3: Research & Grounding (5 Agents)
- **ArXiv Agent (`AA`)**, **CS Agent (`CSA`)**, **Electronics Agent (`EA`)**, **Literature Agent (`LA`)**, **Gap Finder (`GF`)**.

### Layer 4: Synthesis & Structure (4 Agents)
- **Connector (`Conn`)**, **Outline Builder (`OB`)**, **Citation Agent (`Cit`)**, **Critic Agent (`Crit`)**.

### Layer 4.5: Quality Audit & Peer Reviewer (5 Agents)
- **Plagiarism Checker (`PC`)**: Similarity monitor (<15%).
- **Plagiarism Remediator (`PR`)**: Reasoning-driven re-synthesis engine.
- **AI Percentage Auditor (`AI`)**: AI footprint auditor (<10%).
- **Peer Reviewer Agent (`PRV`)**: Evaluates 7 core journal submission questions.
- **Format Quality Auditor (`FQA`)**: Grammar, terminology, and acronym auditor.

### Layer 5: Output Generation (3 Agents)
- **Writer Agent (`WA`)**, **PDF Agent (`PDF`)**, **PPT Agent (`PPT`)**.

### Hugging Face Upskill Integration Engine (`src/core/upskill_engine.py`)
- **AgentTraceLogger**: Captures full execution traces, inputs, outputs, and timestamps across all 27 agents.
- **SkillEvaluator**: Evaluates multi-agent accuracy across 4 academic dimensions (`academic_accuracy`, `citation_grounding`, `structural_coherence`, `reproducibility_score`) ensuring overall accuracy score >= 90.0%.
### Hybrid Mamba-Transformer Neural Engine (`src/core/hybrid_engine.py`)
- **Mamba Linear Scanner (`MambaLinearScanner`)**: $O(N)$ state-space model for rapid ingestion of large codebases and multi-page PDF notes.
- **Transformer Attention Synthesizer (`TransformerAttentionSynthesizer`)**: Dense self-attention QKV engine connecting AST nodes to ArXiv citations.
- **Hybrid Neural Router**: Routes high-volume linear context into self-attention reasoning spaces.
