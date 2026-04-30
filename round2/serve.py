# Run: python round2/serve.py  (then open http://localhost:8765/round2/)
#
# The round2 viewer files (index.html, data.json) live in docs/round2/ now,
# since GitHub Pages serves the site from docs/. This script serves the
# entire docs/ tree locally so you can preview the same URLs that github.io
# exposes — i.e. /round2/, /index.html, /admin.html, /annotate.html.
import os, sys
DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs")
os.chdir(os.path.abspath(DOCS_DIR))
sys.argv = ["server", "8765"]
from http.server import HTTPServer, SimpleHTTPRequestHandler
HTTPServer(("", 8765), SimpleHTTPRequestHandler).serve_forever()
