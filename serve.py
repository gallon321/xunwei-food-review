"""Cross-platform WSGI entry point: python serve.py."""
import os
from waitress import serve
from xunwei import create_app
from xunwei.db import init_db

if __name__ == '__main__':
    application = create_app()
    with application.app_context():
        init_db()
    host = os.environ.get('XUNWEI_HOST', '127.0.0.1')
    port = int(os.environ.get('XUNWEI_PORT', '5000'))
    print(f'Xunwei is running at http://{host}:{port}', flush=True)
    serve(application, host=host, port=port, threads=4)
