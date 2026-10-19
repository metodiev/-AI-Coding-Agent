const $ = (selector) => document.querySelector(selector);
const messages = [];
let settings;

function addTextMessage(role, content) {
  const node = document.createElement("div");
  node.className = `message ${role}`;
  node.textContent = content;
  $("#messages").append(node);
  node.scrollIntoView({ block: "end" });
}

function showError(message) {
  addTextMessage("assistant", `Error: ${message}`);
}

async function refreshModels() {
  const provider = $("#provider").value;
  $("#mode-badge").textContent = provider === "ollama" ? "Local model" : "Cloud model";
  const response = await fetch(`/api/models?provider=${encodeURIComponent(provider)}`);
  const payload = await response.json();
  const select = $("#model");
  select.replaceChildren();
  if (!response.ok) {
    showError(payload.detail || "Could not load models.");
    return;
  }
  for (const name of payload.models) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    select.append(option);
  }
  const preferred = provider === "ollama" ? settings.ollama_model : settings.openai_model;
  if ([...select.options].some((option) => option.value === preferred)) select.value = preferred;
  if (!payload.models.length) select.add(new Option("No Ollama models found", ""));
}

async function loadSettings() {
  const response = await fetch("/api/settings");
  settings = await response.json();
  $("#provider").value = settings.default_provider;
  $("#settings-note").textContent = settings.openai_configured
    ? "OpenAI API key configured."
    : "OpenAI is optional. Set OPENAI_API_KEY in .env to enable it.";
  await refreshModels();
}

function renderTools(events) {
  for (const event of events || []) {
    const node = document.createElement("div");
    node.className = "tool-event";
    const title = document.createElement("strong");
    title.textContent = `Tool: ${event.tool}${event.ok ? "" : " (failed)"}`;
    node.append(title);
    const output = document.createElement("pre");
    output.textContent = event.ok
      ? event.result?.approval_type === "file"
        ? event.result.diff || "(No content changes)"
        : JSON.stringify(event.result, null, 2)
      : event.error;
    node.append(output);
    if (event.result?.approval_required) {
      const approve = document.createElement("button");
      approve.className = "approval";
      approve.textContent = event.result.approval_type === "file"
        ? `Approve file change: ${event.result.path}`
        : `Approve command: ${event.result.command}`;
      approve.addEventListener("click", async () => {
        approve.disabled = true;
        const endpoint = event.result.approval_type === "file"
          ? `/api/files/${event.result.approval_id}/approve`
          : `/api/commands/${event.result.approval_id}/approve`;
        const response = await fetch(endpoint, { method: "POST" });
        const result = await response.json();
        output.textContent = JSON.stringify(result, null, 2);
        if (!response.ok) showError(result.detail || "Command failed.");
      });
      node.append(approve);
    }
    $("#messages").append(node);
  }
}

$("#provider").addEventListener("change", () => refreshModels().catch((error) => showError(error.message)));
$("#refresh-models").addEventListener("click", () => refreshModels().catch((error) => showError(error.message)));
$("#clear-chat").addEventListener("click", () => {
  messages.length = 0;
  $("#messages").replaceChildren();
  $("#messages").innerHTML = '<div class="welcome">New conversation. What would you like to change?</div>';
});

$("#chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const workspace = $("#workspace").value.trim();
  const content = $("#prompt").value.trim();
  if (!workspace) return showError("Enter a workspace folder path first.");
  if (!content) return;
  const send = $("#send");
  send.disabled = true;
  $("#prompt").value = "";
  messages.push({ role: "user", content });
  addTextMessage("user", content);
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workspace,
        provider: $("#provider").value,
        model: $("#model").value || undefined,
        messages,
      }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Request failed.");
    renderTools(result.tool_events);
    addTextMessage("assistant", result.response);
    messages.push({ role: "assistant", content: result.response });
  } catch (error) {
    showError(error.message);
  } finally {
    send.disabled = false;
    $("#prompt").focus();
  }
});

loadSettings().catch((error) => showError(error.message));
