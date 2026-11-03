/* Ledger service worker. The build writes the build id below; a new build means a new
   cache, filled from data/manifest.json at install. The app shell and data are served
   from the cache, so the last build keeps working offline. Data files are refreshed from
   the network when it is available. */
const BUILD = '__BUILD_ID__';
const CACHE = 'ledger-' + BUILD;
const scopeUrl = (p) => new URL(p, self.registration.scope).href;

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    const res = await fetch(scopeUrl('data/manifest.json'), { cache: 'no-store' });
    const manifest = await res.json();
    await cache.put(scopeUrl('data/manifest.json'), new Response(JSON.stringify(manifest), {
      headers: { 'content-type': 'application/json' } }));
    const files = manifest.files.map(scopeUrl).concat([scopeUrl('./'), scopeUrl('sw.js')]);
    // add one by one so a single missing file does not abort the install
    await Promise.all(files.map(async (u) => {
      try { await cache.add(new Request(u, { cache: 'no-store' })); } catch (e) { /* skipped */ }
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k.startsWith('ledger-') && k !== CACHE).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener('message', (event) => {
  if (event.data === 'skipWaiting') self.skipWaiting();
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  const isData = url.pathname.includes('/data/');
  if (req.mode === 'navigate') {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE);
      const cached = await cache.match(scopeUrl('./')) || await cache.match(scopeUrl('index.html'));
      try {
        const fresh = await fetch(req);
        if (fresh.ok) cache.put(scopeUrl('./'), fresh.clone());
        return fresh;
      } catch (e) {
        return cached || Response.error();
      }
    })());
    return;
  }
  if (isData) {
    // network first, cache fallback; keep the cache fresh
    event.respondWith((async () => {
      const cache = await caches.open(CACHE);
      try {
        const fresh = await fetch(req, { cache: 'no-store' });
        if (fresh.ok) cache.put(req, fresh.clone());
        return fresh;
      } catch (e) {
        const cached = await cache.match(req, { ignoreSearch: true });
        return cached || Response.error();
      }
    })());
    return;
  }
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const cached = await cache.match(req, { ignoreSearch: true });
    if (cached) return cached;
    try {
      const fresh = await fetch(req);
      if (fresh.ok) cache.put(req, fresh.clone());
      return fresh;
    } catch (e) {
      return Response.error();
    }
  })());
});
