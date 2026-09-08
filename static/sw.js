/* Service worker — avisos nativos para Tarjeta Ideal (PWA). */
const ICON = "/app/static/icon.png";

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("message", (event) => {
  const data = event.data || {};
  if (data.type !== "TI_SHOW_NOTIFICATIONS") return;
  const alertas = data.alertas || [];
  const tituloApp = data.tituloApp || "Tarjeta Ideal";
  alertas.forEach((a, i) => {
    setTimeout(() => {
      self.registration.showNotification(a.title || tituloApp, {
        body: a.body || "",
        tag: "ti-" + i + "-" + (a.title || ""),
        renotify: true,
        icon: ICON,
        badge: ICON,
        data: { url: "/" },
      });
    }, i * 800);
  });
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      if (list.length > 0) return list[0].focus();
      return self.clients.openWindow("/");
    })
  );
});
