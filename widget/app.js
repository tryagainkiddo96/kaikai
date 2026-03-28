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

// ─── Messages ───
function appendMessage(role, text) {
  const article = document.createElement("article");
  article.className = `message ${role}`;

  const tag = document.createElement("span");
  tag.className = "tag";
  tag.innerHTML = role === "user" ? "YOU" : `<svg class="paw-icon" viewBox="0 0 40 40" style="width:12px;height:12px;color:currentColor"><ellipse cx="20" cy="26" rx="8" ry="7" fill="currentColor"/><ellipse cx="11" cy="15" rx="4.5" ry="5" fill="currentColor" transform="rotate(-15 11 15)"/><ellipse cx="20" cy="11" rx="4" ry="4.5" fill="currentColor"/><ellipse cx="29" cy="15" rx="4.5" ry="5" fill="currentColor" transform="rotate(15 29 15)"/></svg> KAI`;

  const body = document.createElement("p");
  body.textContent = text;

  article.append(tag, body);
  messagesEl.append(article);
  messagesEl.scrollTop = messagesEl.scrollHeight;
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
async function pingHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error("offline");
    healthLabelEl.textContent = "Online";
    healthLabelEl.style.color = "var(--kai-rust)";
    setMood("idle");
  } catch {
    healthLabelEl.textContent = "Offline";
    healthLabelEl.style.color = "var(--kai-red)";
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

// ─── Init ───
pingHealth();
inputEl.focus();

// Hide loading splash
window.addEventListener('load', () => {
  setTimeout(() => {
    document.getElementById('loadingSplash')?.classList.add('hidden');
  }, 600);
});
