// Service worker: cache the app shell so Fresco Scan opens even without network.
const CACHE = 'fresco-scan-v1';
const SHELL = ['./', './index.html', './manifest.json', './icon-192.png', './icon-512.png', './apple-touch-icon.png', './jspdf.umd.min.js'];
self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', e => {
  const req = e.request; if (req.method !== 'GET') return;
  e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {
    // cache CDN libraries (jsPDF, tesseract, fonts) opportunistically
    if (res.ok && (req.url.startsWith(self.location.origin) || /cdnjs|jsdelivr|gstatic|googleapis/.test(req.url))) {
      const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy));
    }
    return res;
  }).catch(() => hit)));
});
