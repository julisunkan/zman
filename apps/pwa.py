"""PWA routes — manifests and service worker for all sub-apps."""
import json
from flask import Blueprint, Response

pwa_bp = Blueprint("pwa", __name__)

def _manifest(name, short_name, start_url, scope, theme, bg, icon_prefix, app_id):
    return {
        "id": app_id,
        "name": name,
        "short_name": short_name,
        "description": f"{name} — powered by Groq AI",
        "start_url": start_url,
        "scope": scope,
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#0a0a0a",
        "theme_color": theme,
        "categories": ["education", "productivity"],
        "icons": [
            {
                "src": f"/static/icons/{icon_prefix}-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any"
            },
            {
                "src": f"/static/icons/{icon_prefix}-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any"
            },
            {
                "src": f"/static/icons/{icon_prefix}-maskable-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "maskable"
            },
            {
                "src": f"/static/icons/{icon_prefix}-maskable-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable"
            },
        ],
        "shortcuts": [],
    }


MANIFESTS = {
    "home": _manifest(
        "AI Tools Suite", "AI Tools",
        "/", "/",
        "#7c3aed", "#0a0a0a", "home",
        "ai-tools-suite"
    ),
    "coursegen": _manifest(
        "Course Generator", "Courses",
        "/coursegen/", "/coursegen/",
        "#3b82f6", "#0a0a0a", "coursegen",
        "ai-tools-course-generator"
    ),
    "emailnewsgen": _manifest(
        "Newsletter Generator", "Newsletter",
        "/emailnewsgen/", "/emailnewsgen/",
        "#22c55e", "#0a0a0a", "emailnewsgen",
        "ai-tools-newsletter-generator"
    ),
    "actgen": _manifest(
        "Activity Book Generator", "Activity Book",
        "/actgen/", "/actgen/",
        "#f59e0b", "#0a0a0a", "actgen",
        "ai-tools-activity-book-generator"
    ),
}


def _json_response(data):
    return Response(
        json.dumps(data, indent=2),
        mimetype="application/manifest+json",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@pwa_bp.route("/manifest.json")
def home_manifest():
    return _json_response(MANIFESTS["home"])


@pwa_bp.route("/coursegen/manifest.json")
def coursegen_manifest():
    return _json_response(MANIFESTS["coursegen"])


@pwa_bp.route("/emailnewsgen/manifest.json")
def emailnewsgen_manifest():
    return _json_response(MANIFESTS["emailnewsgen"])


@pwa_bp.route("/actgen/manifest.json")
def actgen_manifest():
    return _json_response(MANIFESTS["actgen"])


# Service worker served from root so its scope covers the whole origin
SW_JS = r"""
const CACHE = 'ai-tools-v1';
const STATIC = [
  '/static/css/mobile.css',
  '/static/icons/home-192.png',
  '/static/icons/coursegen-192.png',
  '/static/icons/emailnewsgen-192.png',
  '/static/icons/actgen-192.png',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(STATIC)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const { request } = e;
  const url = new URL(request.url);

  // Skip non-GET and cross-origin requests
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;

  // Static assets: cache-first
  if (url.pathname.startsWith('/static/')) {
    e.respondWith(
      caches.match(request).then(cached => cached || fetch(request).then(resp => {
        const clone = resp.clone();
        caches.open(CACHE).then(c => c.put(request, clone));
        return resp;
      }))
    );
    return;
  }

  // HTML pages: network-first, fall back to cache
  e.respondWith(
    fetch(request)
      .then(resp => {
        const clone = resp.clone();
        caches.open(CACHE).then(c => c.put(request, clone));
        return resp;
      })
      .catch(() => caches.match(request))
  );
});
""".strip()


@pwa_bp.route("/sw.js")
def service_worker():
    return Response(
        SW_JS,
        mimetype="application/javascript",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Service-Worker-Allowed": "/",
        },
    )
