// Kill-switch: bản cũ của app từng đăng ký service worker (offline/PWA, nay đã bỏ).
// File này thay thế sw.js cũ để trình duyệt đã cài tự gỡ worker và xoá cache còn sót.
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    for (const k of await caches.keys()) await caches.delete(k)
    await self.registration.unregister()
    for (const c of await self.clients.matchAll({ type: 'window' })) c.navigate(c.url)
  })())
})
