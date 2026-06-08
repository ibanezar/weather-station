const CACHE_STATIC = 'vreme-static-v3';
const CACHE_API    = 'vreme-api-v3';

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
  'cdnjs.cloudflare.com':     7 * 24 * 60 * 60 * 1000, // Chart.js
  'unpkg.com':                7 * 24 * 60 * 60 * 1000, // Leaflet
};

function ttlFor(url) {
  try { return API_TTL[new URL(url).hostname] ?? null; }
  catch { return null; }
}

function isFresh(response) {
  const fetched = response.headers.get('sw-fetched-at');
  if (!fetched) return false;
  const ttl = ttlFor(response.url);
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

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE_STATIC).then(c => c.addAll(['./'])));
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

  // Own origin — network-first, fall back to cache
  if (url.origin === location.origin) {
    e.respondWith(
      fetchAndCache(request, CACHE_STATIC).catch(() => caches.match(request))
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

  // Cloudflare Worker proxy + everything else — network only
  e.respondWith(fetch(request).catch(() => new Response('', { status: 503 })));
});
