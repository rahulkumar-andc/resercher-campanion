# Autonomous Research Companion — System Architecture

## Overview
The Autonomous Research Companion is a 6-layer multi-agent system designed to transform raw code, unstructured notes/PDFs, and high-level research topics into fully-formatted research papers (PDF) and presentations (PPTX).

---

## Architecture Flowchart

```mermaid
flowchart TD
    %% Define Styles (Colors and Shapes)
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
    Sup((Layer 6: Supervisor Agent\nCentral Orchestrator & Router)):::supervisor

    %% LAYER 1: INPUT
    subgraph Layer1 [Layer 1: Input & Parsing]
        direction LR
        DI(Data Ingestor):::l1
        SA(Style Agent):::l1
        QP(Query Parser):::l1
        CI(Code Ingestor):::l1
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
    
    %% LAYER 3: RESEARCH
    subgraph Layer3 [Layer 3: Research & Grounding]
        direction LR
        AA(ArXiv Agent):::l3
        CSA(CS Agent):::l3
        EA(Electronics Agent):::l3
        LA(Literature Agent):::l3
        GF(Gap Finder):::l3
    end
    
    %% LAYER 4: SYNTHESIS
    subgraph Layer4 [Layer 4: Synthesis & Structure]
        direction LR
        Conn(Connector):::l4
        Crit(Critic):::l4
        Cit(Citation):::l4
        OB(Outline Builder):::l4
    end

    %% LAYER 4.5: QUALITY AUDIT
    subgraph Layer45 [Layer 4.5: Quality Audit & Peer Review]
        direction LR
        PC(Plagiarism Checker):::l45
        PR(Plagiarism Remediator):::l45
        AI(AI Percentage Auditor):::l45
        PRV(Peer Reviewer Agent):::l45
        FQA(Format Quality Auditor):::l45
    end
    
    %% LAYER 5: OUTPUT
    subgraph Layer5 [Layer 5: Output Generation]
        direction LR
        WA(Writer Agent):::l5
        PDF(PDF Agent):::l5
        PPT(PPT Agent):::l5
    end
    
    %% Outputs (Deliverables)
    subgraph Deliverables [Final Export]
        direction LR
        OutPDF[(ResearchPaper.pdf)]:::io
        OutPPT[(Presentation.pptx)]:::io
    end

    %% --- CONNECTIONS & DATA FLOW ---
    RawCode --> CI
    RawNotes --> DI & SA
    RawTopic --> QP
    
    Sup <.-> DI & SA & QP & CI
    Sup <.-> CB & AD & CA & HM & BE
    Sup <.-> AA & CSA & EA & LA & GF
    Sup <.-> Conn & Crit & Cit & OB
    Sup <.-> PC & PR & AI & PRV & FQA
    Sup <.-> WA & PDF & PPT
    
    CI --> CB
    DI --> LA
    QP --> AA & CSA & EA & GF
    
    CB & AD & CA & HM & BE --> Conn
    AA & CSA & EA & LA & GF --> Conn
    Conn --> OB & Cit --> WA
    
    WA --> PC & AI & PRV & FQA
    PC & AI -.->|If Rejected: Self-Healing Loop| PR
    PR -.->|Remediated Draft| WA
    
    WA --> PDF & PPT
    PDF --> OutPDF
    PPT --> OutPPT
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

