document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("pipeline-form");
  const topicInput = document.getElementById("topic-input");
  const codeInput = document.getElementById("code-input");
  const notesInput = document.getElementById("notes-input");
  const codeLabel = document.getElementById("code-file-label");
  const notesLabel = document.getElementById("notes-file-label");
  const btnSubmit = document.getElementById("btn-submit");
  const btnSample = document.getElementById("btn-load-sample");
  const terminal = document.getElementById("terminal-logs");
  const jobBadge = document.getElementById("current-job-badge");

  // WebSockets setup
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    appendLog(data);
    updatePipelineNodes(data);
    if (typeof pulseNN === "function") pulseNN();
  };

  function appendLog(log) {
    const line = document.createElement("div");
    line.className = `log-line ${log.level || 'INFO'}`;
    const timestamp = new Date(log.timestamp * 1000).toLocaleTimeString();
    line.textContent = `[${timestamp}] [L${log.layer || 'S'}] ${log.agent_name} | ${log.content}`;
    terminal.appendChild(line);
    terminal.scrollTop = terminal.scrollHeight;
  }

  function updatePipelineNodes(data) {
    if (data.level === "STAGE") {
      const content = data.content.toLowerCase();
      resetNodes();

      if (content.includes("layer 1")) setNodeState(1, "active");
      else if (content.includes("layer 2")) { setNodeState(1, "completed"); setNodeState(2, "active"); }
      else if (content.includes("layer 3")) { setNodeState(1, "completed"); setNodeState(2, "completed"); setNodeState(3, "active"); }
      else if (content.includes("layer 4")) { setNodeState(1, "completed"); setNodeState(2, "completed"); setNodeState(3, "completed"); setNodeState(4, "active"); }
      else if (content.includes("layer 5")) { setNodeState(1, "completed"); setNodeState(2, "completed"); setNodeState(3, "completed"); setNodeState(4, "completed"); setNodeState(5, "active"); }
      else if (content.includes("finished")) {
        for (let i = 1; i <= 5; i++) setNodeState(i, "completed");
        jobBadge.textContent = "Completed ✅";
        btnSubmit.disabled = false;
        btnSubmit.innerHTML = "<span>▶ Execute 6-Layer Multi-Agent Pipeline</span>";
      }
    }
  }

  function resetNodes() {
    for (let i = 1; i <= 5; i++) {
      const node = document.getElementById(`node-layer-${i}`);
      node.classList.remove("active", "completed");
      node.querySelector(".layer-badge").textContent = "Waiting";
    }
  }

  function setNodeState(layerNum, state) {
    const node = document.getElementById(`node-layer-${layerNum}`);
    if (!node) return;
    node.classList.remove("active", "completed");
    node.classList.add(state);
    node.querySelector(".layer-badge").textContent = state.toUpperCase();
  }

  // File selection indicators
  codeInput.addEventListener("change", () => {
    codeLabel.textContent = `${codeInput.files.length} code file(s) selected`;
  });

  notesInput.addEventListener("change", () => {
    notesLabel.textContent = `${notesInput.files.length} notes file(s) selected`;
  });

  // Load sample demo
  btnSample.addEventListener("click", () => {
    topicInput.value = "Autonomous Multi-Agent Architecture for System Code Analysis & Research Synthesis";
    codeLabel.textContent = "Sample Demo: sample_code.py selected";
    notesLabel.textContent = "Sample Demo: sample_notes.txt selected";
  });

  // Form submit
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    if (!topicInput.value.trim()) return;

    btnSubmit.disabled = true;
    btnSubmit.innerHTML = "<span>⚡ Pipeline Executing...</span>";
    jobBadge.textContent = "Executing...";

    const formData = new FormData();
    formData.append("topic", topicInput.value);
    
    const repoUrlInput = document.getElementById("repo-url-input");
    if (repoUrlInput && repoUrlInput.value.trim() !== "") {
        formData.append("repo_url", repoUrlInput.value.trim());
    }

    for (let i = 0; i < codeInput.files.length; i++) {
      formData.append("code_files", codeInput.files[i]);
    }
    for (let i = 0; i < notesInput.files.length; i++) {
      formData.append("notes_files", notesInput.files[i]);
    }

    try {
      const response = await fetch("/api/run", {
        method: "POST",
        body: formData,
      });
      const data = await response.json();
      appendLog({ level: "INFO", layer: "SYS", agent_name: "WebDashboard", content: `Pipeline Job Initiated: ${data.job_id}`, timestamp: Date.now()/1000 });
      checkJobStatus(data.job_id);
    } catch (err) {
      console.error(err);
      jobBadge.textContent = "Error";
      btnSubmit.disabled = false;
      btnSubmit.innerHTML = "<span>▶ Execute 6-Layer Multi-Agent Pipeline</span>";
    }
  });

  async function checkJobStatus(jobId) {
    try {
      const response = await fetch(`/api/job/${jobId}`);
      if (response.ok) {
        const data = await response.json();
        
        if (data.stage === "COMPLETED") {
          if (data.pdf_available) {
             const pdfBtn = document.getElementById("btn-dl-pdf");
             pdfBtn.style.pointerEvents = "auto";
             pdfBtn.style.opacity = "1";
             pdfBtn.href = `/api/download/pdf/${jobId}`;
          }
          if (data.pptx_available) {
             const pptxBtn = document.getElementById("btn-dl-pptx");
             pptxBtn.style.pointerEvents = "auto";
             pptxBtn.style.opacity = "1";
             pptxBtn.href = `/api/download/pptx/${jobId}`;
          }
          return; // Stop polling when complete
        } else if (data.stage === "FAILED") {
          jobBadge.textContent = "Failed";
          return;
        }
      }
    } catch (err) {
      console.error("Status check failed", err);
    }
    
    // Poll every 3 seconds
    setTimeout(() => checkJobStatus(jobId), 3000);
  }

  // --- Exact 27-Agent Neural Topology (D3.js Implementation) ---
  const d3Container = d3.select("#d3-nn-container");
  const width = d3Container.node().getBoundingClientRect().width;
  const height = 400;

  d3Container.selectAll("*").remove(); // Clear on reload

  const svg = d3Container.append("svg")
      .attr("width", "100%")
      .attr("height", height)
      .attr("viewBox", `0 0 ${width} ${height}`)
      .style("background", "transparent");

  const architecture = [
    { layer: 0, name: 'L0: Profiler', agents: ['RPA'], type: 'profiler' },
    { layer: 1, name: 'L1: Input', agents: ['GI', 'CI', 'DI', 'SA', 'QP'], type: 'mamba' },
    { layer: 2, name: 'L2: Analysis', agents: ['CB', 'AD', 'CA', 'HM', 'BE'], type: 'transformer' },
    { layer: 3, name: 'L3: Grounding', agents: ['WSA', 'AA', 'CSA', 'EA', 'LA', 'GF'], type: 'mamba' },
    { layer: 4, name: 'L4: Synthesis', agents: ['Conn', 'OB', 'Cit', 'Crit'], type: 'transformer' },
    { layer: 4.5, name: 'L4.5: Audit', agents: ['PC', 'PR', 'AI', 'PRV', 'FQA'], type: 'transformer' },
    { layer: 5, name: 'L5: Output', agents: ['WA', 'PDF', 'PPT'], type: 'mamba' },
    { layer: 6, name: 'L6: Supervisor', agents: ['Sup'], type: 'supervisor' }
  ];

  let nodes = [];
  let links = [];

  const layerSpacing = width / (architecture.length + 1);
  const maxAgents = 6;
  const nodeSpacing = (height - 80) / maxAgents;

  architecture.forEach((layerData, i) => {
    const numAgents = layerData.agents.length;
    const startY = (height - (numAgents - 1) * nodeSpacing) / 2 + 10;
    
    layerData.agents.forEach((agent, j) => {
      nodes.push({
        id: `${layerData.layer}_${j}`,
        layerIndex: i,
        x: layerSpacing * (i + 1),
        y: startY + (j * nodeSpacing),
        label: agent,
        type: layerData.type
      });
    });
  });

  // Create connections based on Layer 6 Event Bus Architecture
  for (let i = 0; i < architecture.length - 1; i++) {
    const currentLayerAgents = nodes.filter(n => n.layerIndex === i);
    const nextLayerAgents = nodes.filter(n => n.layerIndex === i + 1);
    
    currentLayerAgents.forEach(c => {
      nextLayerAgents.forEach(n => {
        links.push({
          source: c,
          target: n,
          id: `${c.id}-${n.id}`
        });
      });
    });
  }

  // Filters for Glow Effect
  const defs = svg.append("defs");
  const filter = defs.append("filter").attr("id", "glow");
  filter.append("feGaussianBlur").attr("stdDeviation", "4").attr("result", "coloredBlur");
  const feMerge = filter.append("feMerge");
  feMerge.append("feMergeNode").attr("in", "coloredBlur");
  feMerge.append("feMergeNode").attr("in", "SourceGraphic");

  // Draw links
  const linkElements = svg.append("g")
    .selectAll("line")
    .data(links)
    .join("line")
    .attr("x1", d => d.source.x)
    .attr("y1", d => d.source.y)
    .attr("x2", d => d.target.x)
    .attr("y2", d => d.target.y)
    .attr("stroke", "rgba(52, 152, 219, 0.15)")
    .attr("stroke-width", 1);

  // Draw nodes
  const nodeElements = svg.append("g")
    .selectAll("g")
    .data(nodes)
    .join("g")
    .attr("transform", d => `translate(${d.x},${d.y})`);

  nodeElements.append("circle")
    .attr("r", 14)
    .attr("fill", "#1e293b")
    .attr("stroke", d => {
      if (d.type === 'transformer') return '#e74c3c'; // Red for QKV
      if (d.type === 'mamba') return '#2ecc71'; // Green for State-Space
      if (d.type === 'supervisor') return '#f1c40f'; // Yellow for Supervisor
      return '#3498db'; // Blue default
    })
    .attr("stroke-width", 2)
    .attr("class", "node-circle");

  nodeElements.append("text")
    .attr("y", 28)
    .attr("text-anchor", "middle")
    .attr("fill", "#cbd5e1")
    .style("font-size", "11px")
    .style("font-family", "Inter")
    .text(d => d.label);

  // Draw Column Headers
  svg.append("g")
    .selectAll("text")
    .data(architecture)
    .join("text")
    .attr("x", (d, i) => layerSpacing * (i + 1))
    .attr("y", 25)
    .attr("text-anchor", "middle")
    .attr("fill", "rgba(255, 255, 255, 0.6)")
    .style("font-size", "12px")
    .style("font-weight", "bold")
    .style("font-family", "Inter")
    .text(d => d.name);

  // Pulse effect simulation function
  window.pulseNN = function() {
    const activeNodes = d3.shuffle([...nodes]).slice(0, 5);
    
    svg.selectAll(".node-circle")
      .filter(d => activeNodes.includes(d))
      .transition().duration(200)
      .attr("fill", "#8e44ad")
      .attr("stroke", "#fff")
      .style("filter", "url(#glow)")
      .transition().duration(800)
      .attr("fill", "#1e293b")
      .attr("stroke", d => {
        if (d.type === 'transformer') return '#e74c3c';
        if (d.type === 'mamba') return '#2ecc71';
        if (d.type === 'supervisor') return '#f1c40f';
        return '#3498db';
      })
      .style("filter", null);

    const activeLinks = d3.shuffle([...links]).slice(0, 15);
    linkElements
      .filter(d => activeLinks.includes(d))
      .transition().duration(200)
      .attr("stroke", "rgba(142, 68, 173, 0.8)")
      .attr("stroke-width", 3)
      .transition().duration(800)
      .attr("stroke", "rgba(52, 152, 219, 0.15)")
      .attr("stroke-width", 1);
  };

  // Run pulsing automatically for the demo effect
  setInterval(() => {
    window.pulseNN();
  }, 1200);

  // Handle window resizing
  window.addEventListener('resize', () => {
    const newWidth = d3Container.node().getBoundingClientRect().width;
    svg.attr("viewBox", `0 0 ${newWidth} ${height}`);
  });

});
