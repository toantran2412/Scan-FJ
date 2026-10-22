// Service worker: app shell cached for offline use; HTML/manifest fetched network-first so updates arrive on the next open.
const CACHE = 'scan-fj-v13';
const SHELL = ['./', './index.html', './manifest.json', './icon-192.png', './icon-512.png', './apple-touch-icon.png', './jspdf.umd.min.js'];
self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', e => {
  const req = e.request; if (req.method !== 'GET') return;
  const url = new URL(req.url);
  const isShell = req.mode === 'navigate' || /\/(index\.html|manifest\.json)?$/.test(url.pathname);
  if (isShell && url.origin === self.location.origin) {
    // network first, fall back to cache when offline
    e.respondWith(fetch(req, {cache: 'no-cache'}).then(async res => {
        if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); return res; }
        // site gone or erroring (404/5xx): keep running the copy already on the phone
        return (await caches.match(req)) || (await caches.match('./index.html')) || res; })
      .catch(() => caches.match(req).then(hit => hit || caches.match('./index.html'))));
    return;
  }
  e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {
    if (res.ok && (url.origin === self.location.origin || /cdnjs|jsdelivr|unpkg|projectnaptha/.test(req.url))) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
    return res;
  }).catch(() => hit)));
});
