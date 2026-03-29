const messagesEl = document.querySelector("#messages");
const formEl = document.querySelector("#chatForm");
const inputEl = document.querySelector("#promptInput");
const sendButtonEl = document.querySelector("#sendButton");
const healthLabelEl = document.querySelector("#healthLabel");
const moodLabelEl = document.querySelector("#moodLabel");

// ─── Mood System ───
const moods = {
  idle: { label: "Attentive", class: "mood-calm" },
  thinking: { label: "Thinking...", class: "mood-thinking" },
  responding: { label: "Engaged", class: "mood-alert" },
  error: { label: "Concerned", class: "mood-alert" },
};

function setMood(state) {
  const mood = moods[state] || moods.idle;
  moodLabelEl.textContent = mood.label;
  moodLabelEl.className = mood.class;
}

// ─── Message Persistence ───
const STORAGE_KEY = 'kai_chat_history';
const MAX_STORED = 50;

function saveMessages() {
  const messages = messagesEl.querySelectorAll('.message:not(.thinking)');
  const history = [];
  messages.forEach(msg => {
    const role = msg.classList.contains('user') ? 'user' : 'assistant';
    const text = msg.querySelector('p')?.textContent || '';
    if (text && text !== 'Thinking...') {
      history.push({ role, text });
    }
  });
  // Keep last MAX_STORED messages
  const trimmed = history.slice(-MAX_STORED);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
  } catch (e) {
    // Storage full or unavailable — silently skip
  }
}

function loadMessages() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return false;
    const history = JSON.parse(raw);
    if (!Array.isArray(history) || history.length === 0) return false;
    // Clear the default welcome message
    messagesEl.innerHTML = '';
    history.forEach(({ role, text }) => {
      appendMessageNoSave(role, text);
    });
    return true;
  } catch {
    return false;
  }
}

function appendMessageNoSave(role, text) {
  const article = document.createElement("article");
  article.className = `message ${role}`;

  const tag = document.createElement("span");
  tag.className = "tag";
  tag.innerHTML = role === "user" ? "YOU" : `<svg class="paw-icon" viewBox="0 0 40 40" style="width:12px;height:12px;color:currentColor"><ellipse cx="20" cy="26" rx="8" ry="7" fill="currentColor"/><ellipse cx="11" cy="15" rx="4.5" ry="5" fill="currentColor" transform="rotate(-15 11 15)"/><ellipse cx="20" cy="11" rx="4" ry="4.5" fill="currentColor"/><ellipse cx="29" cy="15" rx="4.5" ry="5" fill="currentColor" transform="rotate(15 29 15)"/></svg> KAI`;

  const body = document.createElement("p");
  body.textContent = text;

  const time = document.createElement("span");
  time.className = "msg-time";
  time.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  article.append(tag, body, time);
  messagesEl.append(article);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

// ─── Messages ───
function appendMessage(role, text) {
  appendMessageNoSave(role, text);
  saveMessages();
}

function appendThinking() {
  const article = document.createElement("article");
  article.className = "message assistant thinking";
  article.id = "thinking";

  const tag = document.createElement("span");
  tag.className = "tag";
  tag.innerHTML = `<svg class="paw-icon" viewBox="0 0 40 40" style="width:12px;height:12px;color:currentColor"><ellipse cx="20" cy="26" rx="8" ry="7" fill="currentColor"/><ellipse cx="11" cy="15" rx="4.5" ry="5" fill="currentColor" transform="rotate(-15 11 15)"/><ellipse cx="20" cy="11" rx="4" ry="4.5" fill="currentColor"/><ellipse cx="29" cy="15" rx="4.5" ry="5" fill="currentColor" transform="rotate(15 29 15)"/></svg> KAI`;

  const body = document.createElement("p");
  body.innerHTML = `Thinking<span class="thinking-dots"><span></span><span></span><span></span></span>`;

  article.append(tag, body);
  messagesEl.append(article);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  setMood("thinking");
}

function removeThinking() {
  const el = document.querySelector("#thinking");
  if (el) el.remove();
}

// ─── Health Check ───
let healthCheckInterval = null;

async function pingHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error("offline");
    healthLabelEl.textContent = "Online";
    healthLabelEl.style.color = "var(--kai-rust)";
    setMood("idle");
    // Switch to slower polling when online
    if (healthCheckInterval) {
      clearInterval(healthCheckInterval);
      healthCheckInterval = setInterval(pingHealth, 30000);
    }
  } catch {
    healthLabelEl.textContent = "Reconnecting...";
    healthLabelEl.style.color = "var(--kai-red)";
    // Fast poll when offline
    if (!healthCheckInterval || healthCheckInterval._slow) {
      if (healthCheckInterval) clearInterval(healthCheckInterval);
      healthCheckInterval = setInterval(pingHealth, 3000);
    }
  }
}

// ─── Send ───
async function sendPrompt(prompt) {
  if (!prompt.trim()) return;

  appendMessage("user", prompt);
  inputEl.value = "";
  sendButtonEl.disabled = true;
  appendThinking();

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: prompt }),
    });
    const payload = await response.json();
    removeThinking();

    if (!response.ok) {
      appendMessage("assistant", payload.error || "Connection lost. I'll try again.");
      setMood("error");
      return;
    }

    appendMessage("assistant", payload.reply);
    setMood("responding");
    // Settle back to idle after a moment
    setTimeout(() => setMood("idle"), 3000);
  } catch (error) {
    removeThinking();
    appendMessage("assistant", `Lost connection: ${error.message}`);
    setMood("error");
  } finally {
    sendButtonEl.disabled = false;
    inputEl.focus();
  }
}

// ─── Events ───
formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  await sendPrompt(inputEl.value);
});

inputEl.addEventListener("keydown", async (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    await sendPrompt(inputEl.value);
  }
});

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", async () => {
    await sendPrompt(button.dataset.prompt || "");
  });
});

// Clear chat
document.getElementById("clearChat")?.addEventListener("click", () => {
  if (messagesEl.children.length <= 1) return;
  messagesEl.innerHTML = "";
  appendMessageNoSave("assistant", "Chat cleared. What's next?");
  saveMessages();
});

// Keyboard shortcuts
document.addEventListener("keydown", (e) => {
  // Ctrl+L = clear chat
  if (e.ctrlKey && e.key === "l") {
    e.preventDefault();
    document.getElementById("clearChat")?.click();
  }
  // Ctrl+/ = focus input
  if (e.ctrlKey && e.key === "/") {
    e.preventDefault();
    inputEl.focus();
  }
  // Escape = blur input
  if (e.key === "Escape" && document.activeElement === inputEl) {
    inputEl.blur();
  }
});

// ─── Init ───
const hadHistory = loadMessages();
pingHealth();
healthCheckInterval = setInterval(pingHealth, 30000);
inputEl.focus();

// Hide loading splash
window.addEventListener('load', () => {
  setTimeout(() => {
    document.getElementById('loadingSplash')?.classList.add('hidden');
  }, hadHistory ? 300 : 600);
});

// ─── PWA: Service Worker ───
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").then((reg) => {
    console.log("Kai PWA: service worker registered", reg.scope);
  }).catch((err) => {
    console.warn("Kai PWA: service worker failed", err);
  });
}

// ─── Device Auth ───
const DEVICE_KEY = "kai_device";

function getDevice() {
  try {
    const raw = localStorage.getItem(DEVICE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function saveDevice(device) {
  localStorage.setItem(DEVICE_KEY, JSON.stringify(device));
}

function getDeviceType() {
  const ua = navigator.userAgent;
  if (/iPhone|Android.*Mobile/.test(ua)) return "phone";
  if (/iPad|Android(?!.*Mobile)/.test(ua)) return "tablet";
  return "browser";
}

async function registerDevice() {
  const device = getDevice();
  if (device) return device;

  const name = `${getDeviceType()}-${Date.now().toString(36)}`;
  try {
    const resp = await fetch("/api/device/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_name: name, device_type: getDeviceType() }),
    });
    if (resp.ok) {
      const data = await resp.json();
      saveDevice(data);
      console.log("Kai PWA: device registered", data.device_id);
      return data;
    }
  } catch (e) {
    console.warn("Kai PWA: device registration failed", e);
  }
  return null;
}

async function authenticateDevice() {
  const device = getDevice();
  if (!device) return false;

  try {
    const resp = await fetch("/api/device/auth", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_id: device.device_id, token: device.token }),
    });
    return resp.ok;
  } catch {
    return false;
  }
}

// Register on load
registerDevice().then(() => authenticateDevice());

// ─── Presence: Track Active Device ───
let presenceTimer = null;

function startPresence() {
  if (presenceTimer) return;
  presenceTimer = setInterval(async () => {
    const device = getDevice();
    if (!device) return;
    try {
      await fetch("/api/device/heartbeat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device_id: device.device_id, token: device.token }),
      });
    } catch { /* silent */ }
  }, 30000);
}

// Track visibility — only send heartbeats when visible
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    startPresence();
    pingHealth(); // immediate health check on focus
  }
});

startPresence();

// ─── Push Notifications ───
async function enablePush() {
  if (!("PushManager" in window)) return;

  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: null, // Set VAPID key here when server supports it
  });

  const device = getDevice();
  if (device) {
    await fetch("/api/device/push", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        device_id: device.device_id,
        token: device.token,
        endpoint: JSON.stringify(sub.toJSON()),
      }),
    });
  }
}

// Request push permission after a few interactions
let interactionCount = 0;
formEl.addEventListener("submit", () => {
  interactionCount++;
  if (interactionCount === 3 && "Notification" in window) {
    Notification.requestPermission().then((perm) => {
      if (perm === "granted") enablePush();
    });
  }
});

// ─── Install Prompt ───
let deferredPrompt = null;
window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredPrompt = e;
  // Could show an "Install Kai" button here
  console.log("Kai PWA: install prompt available");
});

window.addEventListener("appinstalled", () => {
  console.log("Kai PWA: installed");
  deferredPrompt = null;
});
