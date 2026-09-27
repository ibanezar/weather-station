// crnivec.si -- samo opozorila (Web Push), brez predpomnjenja.
// Zapiše ga tools/generate_crnivec_page.py (write_site_files) -- ne urejaj ročno.
self.addEventListener('install', function () { self.skipWaiting(); });
self.addEventListener('activate', function (e) { e.waitUntil(self.clients.claim()); });
self.addEventListener('push', function (event) {
  var data = {};
  try { data = event.data ? event.data.json() : {}; } catch (_) {
    data = { body: event.data ? event.data.text() : '' };
  }
  event.waitUntil(self.registration.showNotification(data.title || 'Črnivec', {
    body: data.body || '',
    icon: data.icon || '/icon-192.png',
    tag: data.tag || 'crnivec',
    renotify: true,
    data: { url: data.url || '/' },
    vibrate: [80, 40, 80]
  }));
});
self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  var target = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (list) {
    for (var i = 0; i < list.length; i++) {
      if (list[i].url.indexOf(self.location.origin) === 0 && 'focus' in list[i]) {
        return list[i].navigate ? list[i].navigate(target).then(function (c) { return c && c.focus(); }) : list[i].focus();
      }
    }
    return self.clients.openWindow ? self.clients.openWindow(target) : null;
  }));
});
