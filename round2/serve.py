import os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.argv = ['server', '8765']
from http.server import HTTPServer, SimpleHTTPRequestHandler
HTTPServer(('', 8765), SimpleHTTPRequestHandler).serve_forever()
