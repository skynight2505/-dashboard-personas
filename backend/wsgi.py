import os
import sys
import traceback

_basedir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _basedir)
os.chdir(_basedir)

try:
    from a2wsgi import ASGIMiddleware
    from main import app
    application = ASGIMiddleware(app)
except Exception as e:
    traceback.print_exc()

    def application(environ, start_response):
        status = "500 Internal Server Error"
        headers = [("Content-Type", "text/plain")]
        msg = f"WSGI Error: {e}\n\n{traceback.format_exc()}"
        start_response(status, headers)
        return [msg.encode()]
