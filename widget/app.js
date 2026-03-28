const messagesEl = document.querySelector("#messages");
const formEl = document.querySelector("#chatForm");
const inputEl = document.querySelector("#promptInput");
const sendButtonEl = document.querySelector("#sendButton");
const healthLabelEl = document.querySelector("#healthLabel");

function appendMessage(role, text) {
  const article = document.createElement("article");
  article.className = `message ${role}`;

  const tag = document.createElement("span");
  tag.className = "tag";
  tag.textContent = role === "user" ? "YOU" : "KAI";

  const body = document.createElement("p");
  body.textContent = text;

  article.append(tag, body);
  messagesEl.append(article);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function pingHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) {
      throw new Error("offline");
    }
    healthLabelEl.textContent = "Online";
    healthLabelEl.style.color = "var(--kai-orange)";
  } catch {
    healthLabelEl.textContent = "Offline";
    healthLabelEl.style.color = "var(--kai-red)";
  }
}

async function sendPrompt(prompt) {
  if (!prompt.trim()) {
    return;
  }

  appendMessage("user", prompt);
  inputEl.value = "";
  sendButtonEl.disabled = true;

  // Thinking indicator with warm Shiba vibe
  const thinkingArticle = document.createElement("article");
  thinkingArticle.className = "message assistant";
  thinkingArticle.id = "thinking";
  const thinkingTag = document.createElement("span");
  thinkingTag.className = "tag";
  thinkingTag.textContent = "KAI";
  const thinkingBody = document.createElement("p");
  thinkingBody.textContent = "Thinking...";
  thinkingBody.style.opacity = "0.6";
  thinkingBody.style.fontStyle = "italic";
  thinkingArticle.append(thinkingTag, thinkingBody);
  messagesEl.append(thinkingArticle);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message: prompt }),
    });
    const payload = await response.json();

    // Remove thinking indicator
    const thinking = document.querySelector("#thinking");
    if (thinking) thinking.remove();

    if (!response.ok) {
      appendMessage("assistant", payload.error || "Connection lost. I'll try again.");
      return;
    }

    appendMessage("assistant", payload.reply);
  } catch (error) {
    const thinking = document.querySelector("#thinking");
    if (thinking) thinking.remove();
    appendMessage("assistant", `Lost connection: ${error.message}`);
  } finally {
    sendButtonEl.disabled = false;
    inputEl.focus();
  }
}

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

pingHealth();
inputEl.focus();
