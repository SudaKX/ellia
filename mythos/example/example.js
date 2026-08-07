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
  credits: null,
  hints: [],
  selectedHint: null,
  hintPreview: null,
  hintPending: new Set(),
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
  creditsBalance: document.querySelector("#credits-balance"),
  eventList: document.querySelector("#event-list"),
  fileTree: document.querySelector("#file-tree"),
  hintList: document.querySelector("#hint-list"),
  hintMessage: document.querySelector("#hint-message"),
  hintPreviewContent: document.querySelector("#hint-preview-content"),
  hintPreviewName: document.querySelector("#hint-preview-name"),
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
  state.credits = null;
  state.hints = [];
  state.selectedHint = null;
  state.hintPreview = null;
  state.hintPending = new Set();
  state.lastAttempt = null;
}

function setAuthenticated(token, username) {
  state.token = token;
  state.username = username;
  elements.sessionStatus.textContent = `已认证：${username}`;
  elements.statusDot.className = "status-dot active";
  elements.refreshButton.disabled = false;
  elements.logoutButton.disabled = false;
  elements.accountSection.hidden = false;
}

function clearSession(message = "未认证") {
  state.token = null;
  state.username = "";
  clearWorkspaceData();
  state.currentAccount = null;
  elements.sessionStatus.textContent = message;
  elements.statusDot.className = "status-dot";
  elements.refreshButton.disabled = true;
  elements.logoutButton.disabled = true;
  elements.accountSection.hidden = true;
  elements.accountStatus.textContent = "未选择";
  elements.accountPassword.value = "";
  setNotice(elements.hintMessage, "");
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
    status.textContent = `${event.status}${event.duration === null ? "" : ` ${event.duration}ms`}`;
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
        : `请求失败（状态码 ${response.status}）。`,
    );
    error.status = response.status;
    error.problemType = payload && typeof payload.type === "string" ? payload.type : "";
    throw error;
  }
  return payload;
}

function displayErrorMessage(error) {
  if (error.problemType && error.problemType.endsWith("/access-token-invalid")) {
    return "认证已失效，请重新登录。";
  }
  if (error.problemType && error.problemType.endsWith("/primary-credentials-invalid")) {
    return "用户名或密码不正确。";
  }
  if (error.problemType && error.problemType.endsWith("/virtual-account-invalid-credentials")) {
    return "虚拟账号凭据不正确。";
  }
  if (error.status === 401) {
    return "认证失败，请重新登录。";
  }
  if (error.status === 404) {
    return "请求的资源不存在。";
  }
  if (error.status === 422) {
    return "请求参数无效。";
  }
  return error.message || "请求失败。";
}

async function refreshAccessToken() {
  try {
    const response = await callApi("/auth/refresh", { method: "POST" }, false);
    if (!response.ok) {
      clearSession("会话已过期");
      return false;
    }
    const payload = await readJson(response);
    setAuthenticated(payload.access_token, state.username || "恢复的会话");
    return true;
  } catch (_) {
    clearSession("会话不可用");
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
    const [progress, version, scripts, credits, hints] = await Promise.all([
      callApi("/progress").then(readJson),
      fetchTreeVersion(forceTree),
      callApi("/scripts").then(readJson),
      callApi("/credits").then(readJson),
      callApi("/hints").then(readJson),
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
    state.credits = credits;
    state.hints = hints.hints;
    if (state.selectedHint) {
      state.selectedHint = state.hints.find((hint) => hint.hint_id === state.selectedHint.hint_id) || null;
      if (!state.selectedHint) {
        state.hintPreview = null;
      }
    }
    renderWorkspace();
    return true;
  } catch (error) {
    elements.statusDot.className = "status-dot error";
    setNotice(elements.authMessage, displayErrorMessage(error), "error");
    return false;
  } finally {
    elements.refreshButton.disabled = !state.token;
  }
}

function renderWorkspace() {
  elements.treeVersion.textContent = state.treeVersion || "--";
  renderCredits();
  renderProgress();
  renderScripts();
  renderHints();
  renderFiles();
  renderPreview();
  renderHintPreview();
  renderAnswerForm();
}

function renderCredits() {
  elements.creditsBalance.textContent = state.credits ? `VTB ${state.credits.vtb}` : "VTB --";
}

function renderProgress() {
  elements.progressList.replaceChildren();
  if (!state.progress) {
    const item = document.createElement("li");
    item.innerHTML = "<strong>状态</strong><span>未加载</span>";
    elements.progressList.append(item);
    return;
  }
  const rows = [
    ["已解锁", state.progress.unlocked_nodes.join(", ") || "--"],
    ["前沿", state.progress.frontier_nodes.join(", ") || "--"],
    ["检查点", String(state.progress.checkpoint_sequence)],
    ["版本", String(state.progress.version)],
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
    item.textContent = "暂无脚本";
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
    kind.textContent = `${script.body.kind || "未知"} / 修订版 ${script.revision}`;
    item.append(id, kind);
    elements.scriptList.append(item);
  }
}

function renderHints() {
  elements.hintList.replaceChildren();
  if (!state.token) {
    const notice = document.createElement("p");
    notice.className = "notice";
    notice.textContent = "认证后加载提示。";
    elements.hintList.append(notice);
    return;
  }
  if (!state.hints.length) {
    const notice = document.createElement("p");
    notice.className = "notice";
    notice.textContent = "当前没有可见提示。";
    elements.hintList.append(notice);
    return;
  }
  for (const hint of state.hints) {
    const card = document.createElement("article");
    const header = document.createElement("div");
    const title = document.createElement("strong");
    const price = document.createElement("span");
    const teaser = document.createElement("p");
    const meta = document.createElement("div");
    const status = document.createElement("div");
    const actions = document.createElement("div");
    const pending = state.hintPending.has(hint.hint_id);

    card.className = "hint-card";
    card.dataset.hintId = hint.hint_id;
    header.className = "hint-card-header";
    title.className = "hint-title";
    price.className = "hint-price";
    teaser.className = "hint-teaser";
    meta.className = "hint-meta";
    status.className = `hint-status${hint.disclosed ? " disclosed" : ""}`;
    actions.className = "hint-actions";

    title.textContent = hint.display.title;
    price.textContent = `${hint.vtb_cost} VTB`;
    teaser.textContent = hint.display.teaser || "没有额外说明。";
    meta.textContent = `${hint.media_type} · ${formatBytes(hint.size_bytes)}`;
    status.textContent = pending ? "正在处理..." : hint.disclosed ? "已购买" : "尚未购买";
    if (hint.disclosed) {
      status.textContent += ` · ${hint.content_token.slice(0, 12)}...`;
    }
    header.append(title, price);
    card.append(header, teaser, meta, status, actions);

    const action = document.createElement("button");
    action.type = "button";
    action.className = hint.disclosed ? "primary" : "";
    action.disabled = pending;
    if (hint.disclosed) {
      action.textContent = pending ? "正在读取..." : "揭示内容";
      action.addEventListener("click", () => revealHint(hint));
    } else {
      action.textContent = pending ? "正在购买..." : "购买";
      action.addEventListener("click", () => purchaseHint(hint));
    }
    actions.append(action);
    elements.hintList.append(card);
  }
}

function renderHintPreview() {
  if (!state.hintPreview) {
    elements.hintPreviewName.textContent = "未选择提示";
    elements.hintPreviewContent.textContent = "购买并揭示提示后，内容会显示在这里。";
    return;
  }
  elements.hintPreviewName.textContent = state.hintPreview.name;
  elements.hintPreviewContent.textContent = state.hintPreview.text;
}

function formatBytes(sizeBytes) {
  if (sizeBytes < 1024) {
    return `${sizeBytes} B`;
  }
  return `${(sizeBytes / 1024).toFixed(1)} KB`;
}

function renderFiles() {
  elements.fileTree.replaceChildren();
  if (!state.tree) {
    const notice = document.createElement("p");
    notice.className = "notice";
    notice.textContent = "请先认证以加载文件。";
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
  state.selectedFile = { ...file, text: "正在加载预览...", url: null };
  renderFiles();
  renderPreview();
  try {
    const issued = await callApi(`/files/${file.file_id}/${file.content_token}/content-url`).then(readJson);
    state.selectedFile.url = issued.url;
    const content = await fetch(issued.url, { credentials: "omit" });
    if (!content.ok) {
      throw new Error(`对象请求失败（状态码 ${content.status}）。`);
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
        setNotice(elements.authMessage, "文件已不可用。", "error");
        return;
      }
    }
    state.selectedFile.text = `预览不可用：${error.message}`;
  }
  renderPreview();
}

function renderPreview() {
  if (!state.selectedFile) {
    elements.previewName.textContent = "未选择文件";
    elements.previewContent.textContent = "请从文件树中选择文件。";
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
    setNotice(elements.answerMessage, "暂无答案验证器。", "");
    return;
  }
  elements.answerForm.hidden = false;
  elements.answerForm.dataset.validationId = validator.body.validation_id;
  elements.answerLabel.textContent = "答案";
  elements.answerInput.name = validator.body.input && validator.body.input.name ? validator.body.input.name : "answer";
  elements.answerMeta.textContent = validator.body.validation_id;
  if (!elements.answerMessage.classList.contains("success")) {
    setNotice(elements.answerMessage, "准备就绪。");
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
      setNotice(elements.answerMessage, "答案不正确。", "error");
      return;
    }
    setNotice(elements.answerMessage, "答案已接受，正在刷新运行时状态...", "success");
    await loadWorkspace({ forceTree: true });
    setNotice(elements.answerMessage, "答案已接受。", "success");
  } catch (error) {
    setNotice(elements.answerMessage, displayErrorMessage(error), "error");
    elements.retryAnswer.hidden = false;
  } finally {
    elements.answerSubmit.disabled = false;
  }
}

function hintErrorMessage(error) {
  if (error.problemType && error.problemType.endsWith("/insufficient-credits")) {
    return "VTB 余额不足，提示未购买。";
  }
  if (error.problemType && error.problemType.endsWith("/hint-unavailable")) {
    return "该提示当前不可用。";
  }
  if (error.problemType && error.problemType.endsWith("/hint-content-version-mismatch")) {
    return "提示内容已更新，请刷新后重试。";
  }
  return displayErrorMessage(error);
}

async function purchaseHint(hint) {
  if (state.hintPending.has(hint.hint_id)) {
    return;
  }
  state.hintPending.add(hint.hint_id);
  setNotice(elements.hintMessage, `正在购买“${hint.display.title}”...`);
  renderHints();
  try {
    const payload = await callApi(`/hints/${encodeURIComponent(hint.hint_id)}/disclose`, {
      method: "POST",
      headers: { "Request-ID": crypto.randomUUID() },
    }).then(readJson);
    const disclosed = payload.content.hint;
    state.selectedHint = disclosed;
    state.hints = state.hints.map((item) => item.hint_id === disclosed.hint_id ? disclosed : item);
    setNotice(elements.hintMessage, "提示已购买，可以揭示内容。", "success");
    await loadWorkspace();
  } catch (error) {
    setNotice(elements.hintMessage, hintErrorMessage(error), "error");
  } finally {
    state.hintPending.delete(hint.hint_id);
    renderHints();
    renderHintPreview();
  }
}

async function revealHint(hint) {
  if (state.hintPending.has(hint.hint_id) || !hint.content_token) {
    return;
  }
  state.hintPending.add(hint.hint_id);
  state.selectedHint = hint;
  state.hintPreview = { name: hint.display.title, text: "正在读取提示内容..." };
  setNotice(elements.hintMessage, `正在揭示“${hint.display.title}”...`);
  renderHints();
  renderHintPreview();
  try {
    let currentHint = hint;
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        const issued = await callApi(
          `/hints/${encodeURIComponent(currentHint.hint_id)}/${currentHint.content_token}/content-url`,
        ).then(readJson);
        const content = await fetch(issued.url, { credentials: "omit" });
        if (!content.ok) {
          throw new Error(`对象请求失败（状态码 ${content.status}）。`);
        }
        state.selectedHint = currentHint;
        state.hintPreview = {
          name: currentHint.display.title,
          text: await content.text(),
        };
        setNotice(elements.hintMessage, "提示内容已揭示。", "success");
        return;
      } catch (error) {
        if (attempt === 0 && error.status === 412) {
          const refreshed = await loadWorkspace();
          const refreshedHint = refreshed
            ? state.hints.find((item) => item.hint_id === currentHint.hint_id)
            : null;
          if (refreshedHint && refreshedHint.content_token !== currentHint.content_token) {
            currentHint = refreshedHint;
            continue;
          }
        }
        throw error;
      }
    }
  } catch (error) {
    state.hintPreview = {
      name: hint.display.title,
      text: `提示不可用：${hintErrorMessage(error)}`,
    };
    setNotice(elements.hintMessage, hintErrorMessage(error), "error");
  } finally {
    state.hintPending.delete(hint.hint_id);
    renderHints();
    renderHintPreview();
  }
}

function setAuthMode(mode) {
  state.authMode = mode;
  elements.registerMode.classList.toggle("active", mode === "register");
  elements.loginMode.classList.toggle("active", mode === "login");
  elements.authSubmit.textContent = mode === "register" ? "创建会话" : "登录";
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
    elements.accountStatus.textContent = "未选择";
    elements.accountPassword.value = "";
    setNotice(elements.accountMessage, "");
    setNotice(elements.authMessage, "会话已就绪。", "success");
    clearWorkspaceData();
    renderWorkspace();
    await loadWorkspace({ forceTree: true });
  } catch (error) {
    setNotice(elements.authMessage, displayErrorMessage(error), "error");
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
    elements.accountStatus.textContent = state.currentAccount ? state.currentAccount.display_name : "未选择";
    elements.accountPassword.value = "";
    clearWorkspaceData();
    renderWorkspace();
    setNotice(elements.accountMessage, "账号已激活。", "success");
    await loadWorkspace({ forceTree: true });
  } catch (error) {
    setNotice(elements.accountMessage, displayErrorMessage(error), "error");
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
