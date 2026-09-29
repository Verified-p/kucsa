
/*
============================================================
KUCSA DIGITAL PLATFORM
Progressive Web App - Service Worker
============================================================

Purpose:
- Enable KUCSA PWA functionality
- Cache essential static assets
- Cache official KUCSA app icons
- Provide a safe offline experience
- Always fetch dynamic Django pages from the server
- Never interfere with POST/PUT/PATCH/DELETE requests
- Automatically remove outdated caches

IMPORTANT:
Dynamic/authenticated pages such as:
- Dashboard
- Attendance
- Payments
- Membership
- Announcements
- Events
- Executive information

are NOT intentionally cached.

This helps prevent stale or sensitive information from
being served by the service worker.
============================================================
*/


/*
============================================================
CACHE VERSION
============================================================

Increase this version whenever you make important changes
to cached static assets.

Example:
kucsa-static-v1
kucsa-static-v2
kucsa-static-v3
============================================================
*/

const CACHE_NAME = "kucsa-static-v2";


/*
============================================================
ESSENTIAL STATIC ASSETS
============================================================
*/

const STATIC_ASSETS = [
    "/static/css/style.css",
    "/static/js/app.js",

    /*
    Existing KUCSA favicon / branding
    */
    "/static/images/logoicon.png",
    "/static/images/logokucsaa.png",
    "/static/images/university.png",

    /*
    PWA application icons
    */
    "/static/images/icon-192.png",
    "/static/images/icon-512.png",

    /*
    PWA manifest
    */
    "/static/manifest.json"
];


/*
============================================================
INSTALL
============================================================
*/

self.addEventListener("install", (event) => {

    console.log(
        "[KUCSA SW] Installing:",
        CACHE_NAME
    );

    event.waitUntil(

        caches.open(CACHE_NAME)

            .then((cache) => {

                console.log(
                    "[KUCSA SW] Caching essential assets..."
                );

                return cache.addAll(STATIC_ASSETS);
            })

            .then(() => {

                /*
                Make the new service worker available
                immediately instead of waiting for old tabs
                to close.
                */

                console.log(
                    "[KUCSA SW] Installation complete."
                );

                return self.skipWaiting();
            })

            .catch((error) => {

                console.error(
                    "[KUCSA SW] Installation failed:",
                    error
                );

            })
    );
});


/*
============================================================
ACTIVATE
============================================================
*/

self.addEventListener("activate", (event) => {

    console.log(
        "[KUCSA SW] Activating:",
        CACHE_NAME
    );

    event.waitUntil(

        caches.keys()

            .then((cacheNames) => {

                return Promise.all(

                    cacheNames

                        .filter((cacheName) => {

                            /*
                            Delete every old KUCSA cache.
                            */

                            return cacheName !== CACHE_NAME;
                        })

                        .map((cacheName) => {

                            console.log(
                                "[KUCSA SW] Removing old cache:",
                                cacheName
                            );

                            return caches.delete(cacheName);
                        })
                );
            })

            .then(() => {

                /*
                Immediately take control of pages that are
                already open.
                */

                console.log(
                    "[KUCSA SW] Now controlling KUCSA pages."
                );

                return self.clients.claim();
            })
    );
});


/*
============================================================
FETCH
============================================================

Request strategies:

STATIC ASSETS
--------------
Cache first.
If unavailable, fetch from the network.

HTML / DJANGO PAGES
-------------------
Network first.
Dynamic pages should always receive fresh data.

OTHER GET REQUESTS
------------------
Network first, then cache fallback.

NON-GET REQUESTS
----------------
Ignored completely.

This means the service worker will never interfere with:

POST
PUT
PATCH
DELETE
============================================================
*/

self.addEventListener("fetch", (event) => {

    const request = event.request;


    /*
    ========================================================
    ONLY HANDLE GET REQUESTS
    ========================================================
    */

    if (request.method !== "GET") {
        return;
    }


    /*
    ========================================================
    REQUEST URL
    ========================================================
    */

    const url = new URL(request.url);


    /*
    ========================================================
    SAME-ORIGIN ONLY
    ========================================================

    Requests to external services such as:

    - Bootstrap CDN
    - Google Fonts
    - Other external APIs

    are not controlled by this service worker.
    ========================================================
    */

    if (url.origin !== self.location.origin) {
        return;
    }


    /*
    ========================================================
    STATIC FILES
    ========================================================
    */

    if (
        url.pathname.startsWith("/static/") ||
        url.pathname.startsWith("/media/")
    ) {

        event.respondWith(

            caches.match(request)

                .then((cachedResponse) => {

                    /*
                    Return cached asset immediately when
                    available.
                    */

                    if (cachedResponse) {
                        return cachedResponse;
                    }


                    /*
                    Otherwise request the asset from the
                    server.
                    */

                    return fetch(request)

                        .then((networkResponse) => {

                            /*
                            Cache only successful responses.
                            */

                            if (
                                networkResponse &&
                                networkResponse.ok
                            ) {

                                const responseClone =
                                    networkResponse.clone();

                                caches.open(CACHE_NAME)

                                    .then((cache) => {

                                        cache.put(
                                            request,
                                            responseClone
                                        );

                                    });
                            }

                            return networkResponse;
                        });
                })
        );

        return;
    }


    /*
    ========================================================
    DJANGO HTML PAGES
    ========================================================

    Network first.

    This is intentional.

    KUCSA contains dynamic and potentially sensitive
    information, therefore authenticated pages should
    always attempt to reach the server first.
    ========================================================
    */

    const acceptsHTML =
        request.headers
            .get("accept")
            ?.includes("text/html");


    if (acceptsHTML) {

        event.respondWith(

            fetch(request)

                .then((networkResponse) => {

                    /*
                    Always return the latest server response.
                    */

                    return networkResponse;
                })

                .catch(() => {

                    /*
                    Network unavailable.

                    We only use a previously cached page if
                    one happens to exist.
                    */

                    return caches.match(request)

                        .then((cachedPage) => {

                            if (cachedPage) {
                                return cachedPage;
                            }


                            /*
                            No cached page available.
                            Show KUCSA offline screen.
                            */

                            return createOfflineResponse();
                        });
                })
        );

        return;
    }


    /*
    ========================================================
    OTHER GET REQUESTS
    ========================================================

    Network first with cache fallback.
    ========================================================
    */

    event.respondWith(

        fetch(request)

            .then((networkResponse) => {

                return networkResponse;
            })

            .catch(() => {

                return caches.match(request);
            })
    );

});


/*
============================================================
OFFLINE RESPONSE
============================================================

This response is displayed when:

- The user has no internet connection
- The requested page has never been cached
============================================================
*/

function createOfflineResponse() {

    return new Response(

        `
        <!DOCTYPE html>

        <html lang="en">

        <head>

            <meta charset="UTF-8">

            <meta
                name="viewport"
                content="width=device-width, initial-scale=1.0"
            >

            <meta
                name="theme-color"
                content="#0d6efd"
            >

            <title>
                KUCSA — Offline
            </title>

            <style>

                * {
                    box-sizing: border-box;
                }

                body {
                    margin: 0;
                    min-height: 100vh;

                    display: flex;
                    align-items: center;
                    justify-content: center;

                    padding: 24px;

                    background: #f8f9fa;

                    font-family:
                        -apple-system,
                        BlinkMacSystemFont,
                        "Segoe UI",
                        Roboto,
                        Arial,
                        sans-serif;

                    color: #212529;

                    text-align: center;
                }

                .offline-container {
                    width: 100%;
                    max-width: 440px;

                    background: #ffffff;

                    padding: 40px 28px;

                    border-radius: 20px;

                    box-shadow:
                        0 10px 35px
                        rgba(0, 0, 0, 0.08);
                }

                .offline-logo {
                    width: 110px;
                    height: 110px;

                    object-fit: contain;

                    margin-bottom: 24px;
                }

                h1 {
                    margin: 0 0 12px;

                    font-size: 28px;
                    font-weight: 700;
                }

                p {
                    margin: 0 0 10px;

                    color: #6c757d;

                    line-height: 1.6;

                    font-size: 15px;
                }

                .offline-status {
                    margin-top: 24px;

                    padding: 12px 16px;

                    border-radius: 10px;

                    background: #f1f3f5;

                    font-size: 14px;

                    font-weight: 500;
                }

            </style>

        </head>

        <body>

            <main class="offline-container">

                <img
                    class="offline-logo"
                    src="/static/images/icon-192.png"
                    alt="KUCSA"
                >

                <h1>
                    You're Offline
                </h1>

                <p>
                    The KUCSA Digital Platform needs an
                    internet connection to load this page.
                </p>

                <p>
                    Please reconnect to the internet and
                    try again.
                </p>

                <div class="offline-status">
                    KUCSA Digital Platform
                </div>

            </main>

        </body>

        </html>
        `,

        {
            status: 503,

            headers: {
                "Content-Type": "text/html; charset=UTF-8"
            }
        }
    );
}
