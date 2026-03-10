const CACHE_NAME = 'colosal-v2';
const ASSETS = [
  '/recoleccion/',
  '/static/recoleccion/css/style.css',
  '/static/recoleccion/img/icon-192.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => {
      return response || fetch(event.request);
    })
  );
});
