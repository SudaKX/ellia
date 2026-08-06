const API_BASE = "/api/v1";
const state = {
  authMode: "register",
  username: "",
  currentAccount: null,
  token: null,
  progress: null,
  tree: null,
  treeEtag: null,
  treeVersion: null,
  scripts: [],
  selectedFile: null,
  lastAttempt: null,
  events: [],
};

const elements = {
  accountForm: document.querySelector("#account-form"),
  accountMessage: document.querySelector("#account-message"),
  accountPassword: document.querySelector("#account-password"),
  accountSection: document.querySelector("#account-section"),
  accountStatus: document.querySelector("#account-status"),
  accountSubmit: document.querySelector("#account-submit"),
  accountUsername: document.querySelector("#account-username"),
  answerForm: document.querySelector("#answer-form"),
  answerInput: document.querySelector("#answer-input"),
  answerLabel: document.querySelector("#answer-label"),
  answerMessage: document.querySelector("#answer-message"),
  answerMeta: document.querySelector("#answer-meta"),
  answerSubmit: document.querySelector("#answer-submit"),
  authForm: document.querySelector("#auth-form"),
  authMessage: document.querySelector("#auth-message"),
  authSubmit: document.querySelector("#auth-submit"),
  eventList: document.querySelector("#event-list"),
  fileTree: document.querySelector("#file-tree"),
  loginMode: document.querySelector("#login-mode"),
  logoutButton: document.querySelector("#logout-button"),
  openFileButton: document.querySelector("#open-file-button"),
  password: document.querySelector("#password"),
  previewContent: document.querySelector("#preview-content"),
  previewName: document.querySelector("#preview-name"),
  progressList: document.querySelector("#progress-list"),
  refreshButton: document.querySelector("#refresh-button"),
  registerMode: document.querySelector("#register-mode"),
  retryAnswer: document.querySelector("#retry-answer"),
  scriptList: document.querySelector("#script-list"),
  sessionStatus: document.querySelector("#session-status"),
  statusDot: document.querySelector("#status-dot"),
  treeVersion: document.querySelector("#tree-version"),
  username: document.querySelector("#username"),
};

function setNotice(element, message, tone = "") {
  element.textContent = message;
  element.className = `notice${tone ? ` ${tone}` : ""}`;
}

function clearWorkspaceData() {
  state.progress = null;
  state.tree = null;
  state.treeEtag = null;
  state.treeVersion = null;
  state.scripts = [];
  state.selectedFile = null;
  state.lastAttempt = null;
}

function setAuthenticated(token, username) {
  state.token = token;
  state.username = username;
  elements.sessionStatus.textContent = `Authenticated as ${username}`;
  elements.statusDot.className = "status-dot active";
  elements.refreshButton.disabled = false;
  elements.logoutButton.disabled = false;
  elements.accountSection.hidden = false;
}

function clearSession(message = "Not authenticated") {
  state.token = null;
  state.username = "";
  clearWorkspaceData();
  state.currentAccount = null;
  elements.sessionStatus.textContent = message;
  elements.statusDot.className = "status-dot";
  elements.refreshButton.disabled = true;
  elements.logoutButton.disabled = true;
  elements.accountSection.hidden = true;
  elements.accountStatus.textContent = "Not selected";
  elements.accountPassword.value = "";
  renderWorkspace();
}

function addEvent(method, path, status, duration) {
  state.events.unshift({ method, path, status, duration });
  state.events = state.events.slice(0, 12);
  elements.eventList.replaceChildren();
  for (const event of state.events) {
    const item = document.createElement("li");
    const method = document.createElement("span");
    const path = document.createElement("span");
    const status = document.createElement("span");
    method.className = "method";
    path.className = "path";
    status.className = event.status >= 400 || event.status === "ERR" ? "failed" : "";
    method.textContent = event.method;
    path.textContent = event.path;
    status.textContent = `${event.status}${duration === null ? "" : ` ${duration}ms`}`;
    item.append(method, path, status);
    elements.eventList.append(item);
  }
}

async function callApi(path, options = {}, retryAuth = true) {
  const method = options.method || "GET";
  const headers = new Headers(options.headers || {});
  if (state.token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${state.token}`);
  }
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  const started = performance.now();
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      credentials: "include",
    });
  } catch (error) {
    addEvent(method, path, "ERR", null);
    throw error;
  }
  addEvent(method, path, response.status, Math.round(performance.now() - started));
  const problem = response.status >= 400 ? await response.clone().json().catch(() => null) : null;
  if (
    response.status === 401 &&
    problem &&
    typeof problem.type === "string" &&
    problem.type.endsWith("/access-token-invalid") &&
    retryAuth &&
    path !== "/auth/refresh"
  ) {
    if (await refreshAccessToken()) {
      return callApi(path, options, false);
    }
  }
  return response;
}

async function readJson(response) {
  const payload = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(
      payload && (payload.detail || payload.title)
        ? payload.detail || payload.title
        : `Request failed with ${response.status}.`,
    );
    error.status = response.status;
    throw error;
  }
  return payload;
}

async function refreshAccessToken() {
  try {
    const response = await callApi("/auth/refresh", { method: "POST" }, false);
    if (!response.ok) {
      clearSession("Session expired");
      return false;
    }
    const payload = await readJson(response);
    setAuthenticated(payload.access_token, state.username || "Restored session");
    return true;
  } catch (_) {
    clearSession("Session unavailable");
    return false;
  }
}

async function fetchTreeVersion(forceTree) {
  const options = forceTree || !state.treeEtag
    ? {}
    : { headers: { "If-None-Match": state.treeEtag } };
  const response = await callApi("/files/d/version", options);
  if (response.status === 304) {
    return { unchanged: true, etag: null, treeVersion: null };
  }
  const payload = await readJson(response);
  return {
    unchanged: false,
    etag: response.headers.get("ETag"),
    treeVersion: payload.tree_version,
  };
}

async function loadWorkspace({ forceTree = false } = {}) {
  if (!state.token) {
    return false;
  }
  elements.refreshButton.disabled = true;
  try {
    const [progress, version, scripts] = await Promise.all([
      callApi("/progress").then(readJson),
      fetchTreeVersion(forceTree),
      callApi("/scripts").then(readJson),
    ]);

    const progressChanged = state.progress !== null && state.progress.version !== progress.version;
    const shouldLoadTree = forceTree || !version.unchanged || !state.tree || progressChanged;
    let tree = state.tree;
    if (shouldLoadTree) {
      tree = await callApi("/files/d/tree?path=/").then(readJson);
    }

    state.progress = progress;
    state.treeVersion = tree ? tree.tree_version : state.treeVersion;
    state.tree = tree;
    if (tree) {
      state.treeEtag = tree.tree_version === version.treeVersion && version.etag
        ? version.etag
        : `"${tree.tree_version}"`;
    }
    state.scripts = scripts.items;
    renderWorkspace();
    return true;
  } catch (error) {
    elements.statusDot.className = "status-dot error";
    setNotice(elements.authMessage, error.message, "error");
    return false;
  } finally {
    elements.refreshButton.disabled = !state.token;
  }
}

function renderWorkspace() {
  elements.treeVersion.textContent = state.treeVersion || "--";
  renderProgress();
  renderScripts();
  renderFiles();
  renderPreview();
  renderAnswerForm();
}

function renderProgress() {
  elements.progressList.replaceChildren();
  if (!state.progress) {
    const item = document.createElement("li");
    item.innerHTML = "<strong>Status</strong><span>Not loaded</span>";
    elements.progressList.append(item);
    return;
  }
  const rows = [
    ["Unlocked", state.progress.unlocked_nodes.join(", ") || "--"],
    ["Frontier", state.progress.frontier_nodes.join(", ") || "--"],
    ["Checkpoint", String(state.progress.checkpoint_sequence)],
    ["Version", String(state.progress.version)],
  ];
  for (const [label, value] of rows) {
    const item = document.createElement("li");
    const key = document.createElement("strong");
    const content = document.createElement("span");
    key.textContent = label;
    content.textContent = value;
    item.append(key, content);
    elements.progressList.append(item);
  }
}

function renderScripts() {
  elements.scriptList.replaceChildren();
  if (!state.scripts.length) {
    const item = document.createElement("li");
    item.textContent = "No scripts loaded";
    elements.scriptList.append(item);
    return;
  }
  for (const script of state.scripts) {
    const item = document.createElement("li");
    const id = document.createElement("span");
    const kind = document.createElement("span");
    id.className = "script-id";
    kind.className = "script-kind";
    id.textContent = script.stable_id;
    kind.textContent = `${script.body.kind || "unknown"} / revision ${script.revision}`;
    item.append(id, kind);
    elements.scriptList.append(item);
  }
}

function renderFiles() {
  elements.fileTree.replaceChildren();
  if (!state.tree) {
    const notice = document.createElement("p");
    notice.className = "notice";
    notice.textContent = "Authenticate to load files.";
    elements.fileTree.append(notice);
    return;
  }
  appendDirectory(state.tree, elements.fileTree, true);
}

function appendDirectory(directory, parent, isRoot = false) {
  const container = document.createElement("details");
  container.className = "tree-directory";
  container.open = true;
  const summary = document.createElement("summary");
  summary.textContent = isRoot ? "/" : directory.display.label;
  container.append(summary);
  const children = document.createElement("div");
  children.className = "tree-children";
  for (const child of directory.directories) {
    appendDirectory(child, children);
  }
  for (const file of directory.files) {
    const button = document.createElement("button");
    const kind = document.createElement("span");
    const label = document.createElement("span");
    button.type = "button";
    button.className = `file-button${state.selectedFile && state.selectedFile.file_id === file.file_id ? " selected" : ""}`;
    kind.className = "node-kind";
    kind.textContent = "FILE";
    label.textContent = file.display.label;
    button.append(kind, label);
    button.addEventListener("click", () => openFile(file));
    children.append(button);
  }
  container.append(children);
  parent.append(container);
}

function findFile(directory, fileId) {
  const file = directory.files.find((item) => item.file_id === fileId);
  if (file) {
    return file;
  }
  for (const child of directory.directories) {
    const match = findFile(child, fileId);
    if (match) {
      return match;
    }
  }
  return null;
}

async function openFile(file, retryOnStale = true) {
  state.selectedFile = { ...file, text: "Loading preview...", url: null };
  renderFiles();
  renderPreview();
  try {
    const issued = await callApi(`/files/${file.file_id}/${file.content_token}/content-url`).then(readJson);
    state.selectedFile.url = issued.url;
    const content = await fetch(issued.url, { credentials: "omit" });
    if (!content.ok) {
      throw new Error(`Object request failed with ${content.status}.`);
    }
    state.selectedFile.text = await content.text();
  } catch (error) {
    if (retryOnStale && error.status === 412) {
      const refreshed = await loadWorkspace({ forceTree: true });
      const currentFile = refreshed && state.tree ? findFile(state.tree, file.file_id) : null;
      if (currentFile) {
        await openFile(currentFile, false);
        return;
      }
      if (refreshed) {
        state.selectedFile = null;
        renderFiles();
        renderPreview();
        setNotice(elements.authMessage, "File is no longer available.", "error");
        return;
      }
    }
    state.selectedFile.text = `Preview unavailable: ${error.message}`;
  }
  renderPreview();
}

function renderPreview() {
  if (!state.selectedFile) {
    elements.previewName.textContent = "No file selected";
    elements.previewContent.textContent = "Select a file from the tree.";
    elements.openFileButton.disabled = true;
    return;
  }
  elements.previewName.textContent = state.selectedFile.path;
  elements.previewContent.textContent = state.selectedFile.text;
  elements.openFileButton.disabled = !state.selectedFile.url;
}

function renderAnswerForm() {
  const validator = state.scripts.find((script) => script.body.kind === "answer-validator");
  if (!validator) {
    elements.answerForm.hidden = true;
    setNotice(elements.answerMessage, "No answer validator available.");
    return;
  }
  elements.answerForm.hidden = false;
  elements.answerForm.dataset.validationId = validator.body.validation_id;
  elements.answerLabel.textContent = validator.body.input && validator.body.input.label ? validator.body.input.label : "Answer";
  elements.answerInput.name = validator.body.input && validator.body.input.name ? validator.body.input.name : "answer";
  elements.answerMeta.textContent = validator.body.validation_id;
  if (!elements.answerMessage.classList.contains("success")) {
    setNotice(elements.answerMessage, "Ready.");
  }
}

async function submitAnswer(attempt) {
  elements.answerSubmit.disabled = true;
  elements.retryAnswer.hidden = true;
  try {
    const payload = await callApi(`/validations/${attempt.validationId}/attempts`, {
      method: "POST",
      headers: { "Request-ID": attempt.requestId },
      body: { answer: attempt.answer },
    }).then(readJson);
    if (!payload.content.accepted) {
      setNotice(elements.answerMessage, "Answer rejected.", "error");
      return;
    }
    setNotice(elements.answerMessage, "Accepted. Refreshing runtime state...", "success");
    await loadWorkspace({ forceTree: true });
    setNotice(elements.answerMessage, "Accepted.", "success");
  } catch (error) {
    setNotice(elements.answerMessage, error.message, "error");
    elements.retryAnswer.hidden = false;
  } finally {
    elements.answerSubmit.disabled = false;
  }
}

function setAuthMode(mode) {
  state.authMode = mode;
  elements.registerMode.classList.toggle("active", mode === "register");
  elements.loginMode.classList.toggle("active", mode === "login");
  elements.authSubmit.textContent = mode === "register" ? "Create session" : "Log in";
  setNotice(elements.authMessage, "");
}

elements.registerMode.addEventListener("click", () => setAuthMode("register"));
elements.loginMode.addEventListener("click", () => setAuthMode("login"));
elements.refreshButton.addEventListener("click", () => loadWorkspace());
elements.openFileButton.addEventListener("click", () => {
  if (state.selectedFile && state.selectedFile.url) {
    window.open(state.selectedFile.url, "_blank", "noopener");
  }
});
elements.logoutButton.addEventListener("click", async () => {
  try {
    await callApi("/auth/logout", { method: "POST" }).then(readJson);
  } catch (_) {
    // Clearing local state is still correct after an unavailable logout request.
  }
  clearSession();
});
elements.authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const username = elements.username.value.trim();
  const password = elements.password.value;
  elements.authSubmit.disabled = true;
  try {
    const path = state.authMode === "register" ? "/auth/register" : "/auth/login";
    const payload = await callApi(path, { method: "POST", body: { username, password } }).then(readJson);
    setAuthenticated(payload.access_token, username);
    state.currentAccount = null;
    elements.accountStatus.textContent = "Not selected";
    elements.accountPassword.value = "";
    setNotice(elements.accountMessage, "");
    setNotice(elements.authMessage, "Session ready.", "success");
    clearWorkspaceData();
    renderWorkspace();
    await loadWorkspace({ forceTree: true });
  } catch (error) {
    setNotice(elements.authMessage, error.message, "error");
  } finally {
    elements.authSubmit.disabled = false;
  }
});
elements.accountForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  elements.accountSubmit.disabled = true;
  try {
    const payload = await callApi("/vac/login", {
      method: "POST",
      headers: { "Request-ID": crypto.randomUUID() },
      body: {
        username: elements.accountUsername.value.trim(),
        password: elements.accountPassword.value,
      },
    }).then(readJson);
    state.currentAccount = payload.content.current_account;
    elements.accountStatus.textContent = state.currentAccount ? state.currentAccount.display_name : "Not selected";
    elements.accountPassword.value = "";
    clearWorkspaceData();
    renderWorkspace();
    setNotice(elements.accountMessage, "Account active.", "success");
    await loadWorkspace({ forceTree: true });
  } catch (error) {
    setNotice(elements.accountMessage, error.message, "error");
  } finally {
    elements.accountSubmit.disabled = false;
  }
});
elements.answerForm.addEventListener("submit", (event) => {
  event.preventDefault();
  state.lastAttempt = {
    answer: elements.answerInput.value,
    requestId: crypto.randomUUID(),
    validationId: elements.answerForm.dataset.validationId,
  };
  submitAnswer(state.lastAttempt);
});
elements.retryAnswer.addEventListener("click", () => {
  if (state.lastAttempt) {
    submitAnswer(state.lastAttempt);
  }
});

elements.username.value = `example-${Math.random().toString(36).slice(2, 10)}`;
elements.password.value = "example-pass-123";
renderWorkspace();
refreshAccessToken().then((restored) => restored && loadWorkspace());
