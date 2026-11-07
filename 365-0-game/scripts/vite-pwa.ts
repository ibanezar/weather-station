// A small Vite plugin for the two build-time jobs of the PWA:
//  1. preload the two fonts the first screen needs (the display font and the UI regular weight);
//  2. emit sw.js with the exact list of files to precache, so the game works offline after one visit.
// It replaces a PWA framework: the service worker is about thirty lines and has no runtime dependency.
import { createHash } from 'node:crypto';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import type { Plugin } from 'vite';

function listFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name);
    return statSync(full).isDirectory() ? listFiles(full) : [full];
  });
}

/** The service worker. __VERSION__ and __PRECACHE__ are filled in at build time. */
export const SW_TEMPLATE = `// Generated at build time. Do not edit.
const VERSION = '__VERSION__';
const CACHE = '365-0-' + VERSION;
const PRECACHE = __PRECACHE__;

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(PRECACHE))
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
`;

export function buildServiceWorker(precache: string[], version: string): string {
  return SW_TEMPLATE.replace('__VERSION__', version).replace(
    '__PRECACHE__',
    JSON.stringify(precache, null, 2),
  );
}

export function pwa(projectRoot: string): Plugin {
  const publicDir = join(projectRoot, 'public');
  return {
    name: 'pwa',
    apply: 'build',
    transformIndexHtml: {
      order: 'post',
      handler(_html, ctx) {
        const bundle = ctx.bundle;
        if (!bundle) return undefined;
        const wanted = [
          'big-shoulders-display-latin-wght-normal',
          'instrument-sans-latin-wght-normal',
        ];
        const tags = Object.keys(bundle)
          .filter((file) => wanted.some((w) => file.includes(w)) && file.endsWith('.woff2'))
          .map((file) => ({
            tag: 'link',
            attrs: {
              rel: 'preload',
              as: 'font',
              type: 'font/woff2',
              crossorigin: '',
              href: `./${file}`,
            },
            injectTo: 'head' as const,
          }));
        return tags;
      },
    },
    generateBundle(_options, bundle) {
      const built = Object.keys(bundle).filter((f) => !f.endsWith('.map'));
      const publicFiles = listFiles(publicDir).map((f) => relative(publicDir, f));
      const hash = createHash('sha256');
      for (const f of [...built].sort()) hash.update(f);
      // The page itself is not part of the bundle at this point, but it must be precached (and a change
      // to it must change the version), so its source is hashed too.
      hash.update(readFileSync(join(projectRoot, 'index.html')));
      for (const f of publicFiles.sort()) {
        hash.update(f);
        hash.update(readFileSync(join(publicDir, f)));
      }
      const precache = [...built, ...publicFiles, 'index.html']
        .filter((f) => f !== 'sw.js')
        .map((f) => `./${f}`)
        .filter((f, i, all) => all.indexOf(f) === i)
        .sort();
      this.emitFile({
        type: 'asset',
        fileName: 'sw.js',
        source: buildServiceWorker(precache, hash.digest('hex').slice(0, 12)),
      });
    },
  };
}
