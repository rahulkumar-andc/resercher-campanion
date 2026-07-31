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
    classDef l5 fill:#34495e,stroke:#2c3e50,color:white;
    classDef io fill:#95a5a6,stroke:#7f8c8d,color:black,stroke-dasharray: 5 5;
    
    %% Inputs (User Data)
    subgraph IODisks [User Input Sources]
        direction LR
        RawCode[(Raw Source Code)]:::io
        RawNotes[(PDFs & User Notes)]:::io
        RawTopic[(Topic String)]:::io
    end
    
    %% Central Hub / Brain (Like the NATS Event Bus)
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

    %% 1. Input to L1
    RawCode --> CI
    RawNotes --> DI
    RawNotes --> SA
    RawTopic --> QP
    
    %% 2. Neural/Bus Connections (Supervisor monitoring everything)
    Sup <.-> DI & SA & QP & CI
    Sup <.-> CB & AD & CA & HM & BE
    Sup <.-> AA & CSA & EA & LA & GF
    Sup <.-> Conn & Crit & Cit & OB
    Sup <.-> WA & PDF & PPT
    
    %% 3. Logical Flow: Layer 1 to Layer 2/3/5
    CI -->|Preprocessed Code| CB
    DI -->|Notes JSON| LA
    QP -->|Subtopics| AA & CSA & EA & GF
    SA -.->|Style Fingerprint Bypass| WA
    
    %% 4. Logical Flow: Layer 2 to Layer 3
    CB -->|Function Blocks| AA
    AD -->|Detected Algorithms| CSA
    HM -->|Circuit Logic| EA
    BE -->|Code Weaknesses| GF
    CA -.->|"O(N) Complexities"| Conn
    
    %% 5. Logical Flow: Layer 3 to Layer 4
    AA & CSA & EA & LA & GF -->|Research Data| Conn
    GF -->|Novelty Gap| OB
    AA -->|Raw BibTeX| Cit
    
    %% 6. Logical Flow: Layer 4 to Layer 5
    Conn -->|Unified Context| WA
    OB -->|Document Sections| WA
    Cit -->|IEEE/ACM Refs| WA
    WA <-->|Devil's Advocate Loop| Crit
    
    %% 7. Logical Flow: Layer 5 to Export
    WA -->|Final Text Draft| PDF & PPT
    PDF --> OutPDF
    PPT --> OutPPT
```

---

## Layer Breakdown

### Layer 6: Central Orchestrator & Router (Supervisor Agent)
- **Role**: Serves as the system brain and event bus (NATS-compatible).
- **Function**: Continuously monitors state and routes data between layers asynchronously.

### Layer 1: Input & Parsing
- **Code Ingestor (`CI`)**: Parses raw source code.
- **Data Ingestor (`DI`)**: Extracts structured text and metadata from PDFs and user notes.
- **Style Agent (`SA`)**: Captures user writing style fingerprints.
- **Query Parser (`QP`)**: Deconstructs raw topics into targeted sub-queries.

### Layer 2: Code Analysis
- **Code Breaker (`CB`)**: Breaks code into function blocks.
- **Algo Detector (`AD`)**: Identifies core algorithms and techniques.
- **Complexity Analyzer (`CA`)**: Calculates Big-O space/time complexity.
- **HW Mapper (`HM`)**: Maps hardware and circuit abstractions.
- **Bug & Edge Case (`BE`)**: Spots code weaknesses and edge conditions.

### Layer 3: Research & Grounding
- **ArXiv Agent (`AA`)**: Fetches academic literature and BibTeX citations.
- **CS Agent (`CSA`)**: Researches Computer Science fundamentals and state-of-the-art benchmarks.
- **Electronics Agent (`EA`)**: Explores hardware/electronics domain knowledge.
- **Literature Agent (`LA`)**: Analyzes notes and background material.
- **Gap Finder (`GF`)**: Identifies novel gaps between code weaknesses and existing literature.

### Layer 4: Synthesis & Structure
- **Connector (`Conn`)**: Synthesizes unified context across research and code analysis.
- **Outline Builder (`OB`)**: Constructs paper/presentation sections based on novelty gaps.
- **Citation Agent (`Cit`)**: Formats BibTeX references into IEEE/ACM styles.
- **Critic Agent (`Crit`)**: Performs iterative "Devil's Advocate" reviews on writer drafts.

### Layer 5: Output Generation
- **Writer Agent (`WA`)**: Drafts main text using styled fingerprint guidelines.
- **PDF Agent (`PDF`)**: Compiles final manuscript into `ResearchPaper.pdf`.
- **PPT Agent (`PPT`)**: Generates structured slides into `Presentation.pptx`.
