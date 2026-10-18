// HTML-ToDo-App service worker: makes the app installable. Deliberately caches NOTHING —
// page loads go straight to the network, so the installed app always runs the latest version
// (offline support is a later item, storage-spec S-8). API calls (OneDrive) are not touched.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', e => {
  if (e.request.mode === 'navigate') e.respondWith(fetch(e.request));
});
