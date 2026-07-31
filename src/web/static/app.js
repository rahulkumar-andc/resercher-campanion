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

    for (let i = 0; i < codeInput.files.length; i++) {
      formData.append("code_files", codeInput.files[i]);
    }
    for (let i = 0; i < notesInput.files.length; i++) {
      formData.append("notes_files", notesInput.files[i]);
    }

    try {
      const resp = await fetch("/api/run", {
        method: "POST",
        body: formData
      });
      const data = await resp.json();
      appendLog({
        agent_name: "SupervisorAgent",
        layer: 6,
        content: `Job ${data.job_id} submitted successfully.`,
        level: "INFO",
        timestamp: Date.now() / 1000
      });
    } catch (err) {
      alert("Error starting pipeline: " + err.message);
      btnSubmit.disabled = false;
      btnSubmit.innerHTML = "<span>▶ Execute 6-Layer Multi-Agent Pipeline</span>";
    }
  });
});
