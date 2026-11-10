// Generated at build time. Do not edit.
const VERSION = 'd2c9d7630e89';
const CACHE = '365-0-' + VERSION;
const PRECACHE = [
  "./assets/big-shoulders-display-latin-ext-wght-normal-EP2r9iG4.woff2",
  "./assets/big-shoulders-display-latin-wght-normal-Bn_gnr7w.woff2",
  "./assets/index-C4fEVQNj.js",
  "./assets/index-DVhxjXOA.css",
  "./assets/instrument-sans-latin-ext-wght-normal-B5bTHO_g.woff2",
  "./assets/instrument-sans-latin-wght-normal-BbzFLZTg.woff2",
  "./assets/styleguide-IjoPWN_W.js",
  "./data/mystery.v1.json",
  "./data/world.v1.json",
  "./favicon.svg",
  "./icons/apple-touch-icon.png",
  "./icons/favicon-32.png",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/icon-maskable-512.png",
  "./icons/icon.svg",
  "./index.html",
  "./manifest.webmanifest",
  "./og.png"
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      // cache: 'reload' skips the browser's HTTP cache, so a fresh deploy is never precached from stale copies.
      .then((cache) => cache.addAll(PRECACHE.map((url) => new Request(url, { cache: 'reload' }))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k.startsWith('365-0-') && k !== CACHE).map((k) => caches.delete(k))),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  if (new URL(request.url).origin !== self.location.origin) return;
  // Page loads: the app shell, from the cache first so the game opens offline.
  if (request.mode === 'navigate') {
    event.respondWith(caches.match('./index.html', { ignoreVary: true }).then((hit) => hit || fetch(request)));
    return;
  }
  // Everything else: the cache first, then the network (and remember what the network returned).
  event.respondWith(
    // ignoreVary: module scripts and fonts send an Origin header, so a response that says Vary: Origin
    // would otherwise never match the entry the install step stored without one.
    caches.match(request, { ignoreVary: true }).then(
      (hit) =>
        hit ||
        fetch(request).then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        }),
    ),
  );
});
