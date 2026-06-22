const CACHE_STATIC = 'vreme-static-v12';
const CACHE_API    = 'vreme-api-v12';

// Stale-while-revalidate TTLs per host (ms)
const API_TTL = {
  'api.open-meteo.com':             5 * 60 * 1000,  // 5 min
  'marine-api.open-meteo.com':     15 * 60 * 1000,  // 15 min
  'air-quality-api.open-meteo.com':15 * 60 * 1000,
  'flood-api.open-meteo.com':      30 * 60 * 1000,
  'climate-api.open-meteo.com':    60 * 60 * 1000,  // 1 h
  'seasonal-api.open-meteo.com':   60 * 60 * 1000,
  'fonts.googleapis.com':     7 * 24 * 60 * 60 * 1000, // 7 days
  'fonts.gstatic.com':        7 * 24 * 60 * 60 * 1000,
  'cdnjs.cloudflare.com':     7 * 24 * 60 * 60 * 1000, // Chart.js (if cached)
  'unpkg.com':                7 * 24 * 60 * 60 * 1000, // Leaflet (if cached)
};

// Own-origin HTML/assets: stale-while-revalidate TTL (90 s)
const OWN_TTL = 90 * 1000;

function ttlFor(url, responseHeaders) {
  try {
    const hostname = new URL(url).hostname;
    if (API_TTL[hostname] !== undefined) return API_TTL[hostname];
    // Respect Cache-Control: max-age for other hosts (e.g. Cloudflare Worker)
    if (responseHeaders) {
      const cc = responseHeaders.get('cache-control') || '';
      if (/no-store|no-cache/.test(cc)) return null;
      const m = cc.match(/\bmax-age=(\d+)\b/);
      if (m) { const s = parseInt(m[1], 10); if (s > 0) return s * 1000; }
    }
    return null;
  } catch { return null; }
}

function isFresh(response) {
  const fetched = response.headers.get('sw-fetched-at');
  if (!fetched) return false;
  const ttl = ttlFor(response.url, response.headers);
  return ttl !== null && (Date.now() - parseInt(fetched, 10)) < ttl;
}

async function fetchAndCache(request, cacheName) {
  const res = await fetch(request);
  if (!res.ok) return res;
  const headers = new Headers(res.headers);
  headers.set('sw-fetched-at', String(Date.now()));
  const stamped = new Response(await res.clone().arrayBuffer(), {
    status: res.status, statusText: res.statusText, headers,
  });
  caches.open(cacheName).then(c => c.put(request, stamped));
  return res;
}

const LONG_LIVED_HOSTS = new Set([
  'fonts.googleapis.com', 'fonts.gstatic.com',
  'cdnjs.cloudflare.com', 'unpkg.com',
]);

async function refreshStaleCache() {
  const cache = await caches.open(CACHE_API);
  const requests = await cache.keys();
  await Promise.allSettled(requests
    .filter(req => {
      try { return !LONG_LIVED_HOSTS.has(new URL(req.url).hostname); }
      catch { return false; }
    })
    .map(async req => {
      const cached = await cache.match(req);
      if (!cached) return;
      const fetchedAt = parseInt(cached.headers.get('sw-fetched-at') || '0', 10);
      const ttl = ttlFor(req.url, cached.headers);
      if (!ttl || !fetchedAt) return;
      if ((Date.now() - fetchedAt) > ttl * 0.5) {
        await fetchAndCache(req, CACHE_API).catch(() => {});
      }
    })
  );
}

self.addEventListener('message', event => {
  if (event.data?.type === 'REFRESH_CACHE') {
    event.waitUntil(refreshStaleCache());
  }
});

self.addEventListener('periodicsync', event => {
  if (event.tag === 'weather-refresh') {
    event.waitUntil(refreshStaleCache());
  }
});

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE_STATIC).then(c => c.addAll(['./', './app.js', './manifest.json'])));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_STATIC && k !== CACHE_API).map(k => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  const { request } = e;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);

  // HTML navigacije (app shell) — network-first, da uporabnik VEDNO dobi
  // svežo verzijo. Cache je le offline fallback. Brez tega je SW serviral
  // staro index.html in popravki niso prišli do uporabnika.
  if (url.origin === location.origin &&
      (request.mode === 'navigate' || request.destination === 'document')) {
    e.respondWith(
      fetchAndCache(request, CACHE_STATIC).catch(() =>
        caches.open(CACHE_STATIC)
          .then(c => c.match(request))
          .then(r => r ?? new Response('', { status: 503 }))
      )
    );
    return;
  }

  // Ostali own-origin viri — stale-while-revalidate (90 s TTL za hitre ponovne nalaganja)
  if (url.origin === location.origin) {
    e.respondWith(
      caches.open(CACHE_STATIC).then(async cache => {
        const cached = await cache.match(request);
        const age = cached ? parseInt(cached.headers.get('sw-fetched-at') || '0', 10) : 0;
        const fresh = age && (Date.now() - age) < OWN_TTL;
        if (cached && fresh) {
          fetchAndCache(request, CACHE_STATIC).catch(() => {}); // background refresh
          return cached;
        }
        return fetchAndCache(request, CACHE_STATIC)
          .catch(() => cached ?? new Response('', { status: 503 }));
      })
    );
    return;
  }

  // Known third-party hosts — stale-while-revalidate
  if (ttlFor(request.url) !== null) {
    e.respondWith(
      caches.open(CACHE_API).then(async cache => {
        const cached = await cache.match(request);
        if (cached && isFresh(cached)) {
          fetchAndCache(request, CACHE_API).catch(() => {}); // background refresh
          return cached;
        }
        return fetchAndCache(request, CACHE_API)
          .catch(() => cached ?? new Response('', { status: 503 }));
      })
    );
    return;
  }

  // Everything else (Cloudflare Worker proxy etc.) — network with max-age caching
  e.respondWith(
    caches.open(CACHE_API).then(async cache => {
      const cached = await cache.match(request);
      if (cached && isFresh(cached)) {
        fetchAndCache(request, CACHE_API).catch(() => {}); // background refresh
        return cached;
      }
      const res = await fetch(request).catch(() => null);
      if (!res) return cached ?? new Response('', { status: 503 });
      // Only cache if response has a positive max-age
      const ttl = ttlFor(request.url, res.headers);
      if (ttl && ttl > 0) {
        const headers = new Headers(res.headers);
        headers.set('sw-fetched-at', String(Date.now()));
        const stamped = new Response(await res.clone().arrayBuffer(), {
          status: res.status, statusText: res.statusText, headers,
        });
        cache.put(request, stamped);
      }
      return res;
    })
  );
});
