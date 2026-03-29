// Kai PWA Service Worker
// Handles offline caching and push notifications

const CACHE_NAME = "kai-v1";
const STATIC_ASSETS = [
  "/",
  "/index.html",
  "/styles.css",
  "/app.js",
  "/kai-logo.svg",
  "/paw.svg",
  "/favicon.svg",
  "/manifest.json",
];

// Install — cache static assets
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// Activate — clean old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch — network first, fall back to cache
self.addEventListener("fetch", (event) => {
  // Skip non-GET and WebSocket
  if (event.request.method !== "GET") return;
  if (event.request.url.includes("/ws")) return;

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Cache successful responses
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});

// Push notifications
self.addEventListener("push", (event) => {
  let data = { title: "Kai", body: "Something happened.", tag: "kai-update" };

  if (event.data) {
    try {
      data = event.data.json();
    } catch {
      data.body = event.data.text();
    }
  }

  const options = {
    body: data.body,
    icon: "/kai-logo.svg",
    badge: "/favicon.svg",
    tag: data.tag || "kai-update",
    vibrate: [100, 50, 100],
    data: data,
    actions: [
      { action: "open", title: "Open" },
      { action: "dismiss", title: "Dismiss" },
    ],
  };

  event.waitUntil(self.registration.showNotification(data.title, options));
});

// Notification click
self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  if (event.action === "dismiss") return;

  event.waitUntil(
    clients.matchAll({ type: "window" }).then((clientList) => {
      // Focus existing window if open
      for (const client of clientList) {
        if (client.url.includes("/") && "focus" in client) {
          return client.focus();
        }
      }
      // Open new window
      return clients.openWindow("/");
    })
  );
});

// Background sync (for offline message queue)
self.addEventListener("sync", (event) => {
  if (event.tag === "send-message") {
    event.waitUntil(syncMessages());
  }
});

async function syncMessages() {
  // Pull queued messages from IndexedDB and send when back online
  // Implementation depends on message storage
}
