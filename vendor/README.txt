MapLibre GL JS 5.6.2

These distribution files are pinned locally so the estate planner does not need
a third-party CDN to load the map viewer library:

- maplibre-gl.js
- maplibre-gl.css

Upstream: https://github.com/maplibre/maplibre-gl-js
Package: https://www.npmjs.com/package/maplibre-gl
License: 3-Clause BSD; see MAPLIBRE-LICENSE.txt.

The viewer's USGS imagery/topographic maps, AWS elevation tiles, and optional
OpenStreetMap references are still fetched from their public services and need
an internet connection.

PDF.js 6.4.299 (legacy build)

Used by the Estimator to open blueprint PDFs locally in the browser. Files are
never uploaded unless you choose "Read with AI".

- pdfjs/pdf.min.mjs
- pdfjs/pdf.worker.min.mjs
- pdfjs/standard_fonts/

Upstream: https://github.com/mozilla/pdf.js
Package: https://www.npmjs.com/package/pdfjs-dist
License: Apache-2.0; see pdfjs/LICENSE.txt.
