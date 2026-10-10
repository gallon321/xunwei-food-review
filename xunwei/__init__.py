"""Application factory. No database writes happen merely by importing this package."""
import os
import secrets
from pathlib import Path
from flask import Flask, jsonify, render_template

ROOT = Path(__file__).resolve().parent.parent


def create_app(config=None):
    app = Flask(__name__, template_folder=str(ROOT / 'templates'), static_folder=str(ROOT / 'static'))
    production = os.environ.get('XUNWEI_ENV') == 'production'
    app.config.from_mapping(
        DATABASE=os.environ.get('XUNWEI_DATABASE', str(ROOT / 'xunwei.db')),
        SECRET_KEY=os.environ.get('SECRET_KEY'), SEED_DEMO=False,
        CSRF_ENABLED=True, REVIEWS_PER_PAGE=5,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=production, MAX_CONTENT_LENGTH=65536,
        PRODUCTION=production,
    )
    if config:
        app.config.update(config)
    if not app.config['SECRET_KEY']:
        if app.config['PRODUCTION']:
            raise RuntimeError('Production requires a SECRET_KEY of at least 32 characters.')
        if app.testing:
            app.config['SECRET_KEY'] = secrets.token_hex(32)
        else:
            instance = ROOT / 'instance'
            instance.mkdir(exist_ok=True)
            keyfile = instance / 'secret.key'
            try:
                with keyfile.open('x', encoding='utf-8') as handle:
                    handle.write(secrets.token_hex(32))
            except FileExistsError:
                pass
            app.config['SECRET_KEY'] = keyfile.read_text(encoding='utf-8').strip()
    if app.config['PRODUCTION'] and (len(app.config['SECRET_KEY']) < 32 or app.config['SEED_DEMO']):
        raise RuntimeError('Production requires a strong secret and SEED_DEMO=False.')

    from . import accounts, admin, catalog, favorites, reviews, discovery
    from .db import close_db, get_db
    from .security import load_user_and_csrf, inject_globals
    for module in (accounts, admin, catalog, favorites, reviews, discovery):
        app.register_blueprint(module.bp)
    app.teardown_appcontext(close_db)
    app.before_request(load_user_and_csrf)
    app.context_processor(inject_globals)

    messages = {400: '提交内容无效或页面已过期，请刷新重试', 403: '你没有权限访问这个页面',
                404: '页面或内容不存在', 413: '提交内容过大', 429: '尝试过于频繁，请稍后重试',
                500: '服务暂时不可用，请稍后重试'}
    def error_page(error):
        code = getattr(error, 'code', 500)
        return render_template('error.html', code=code, message=messages[code]), code
    for code in messages:
        app.register_error_handler(code, error_page)

    @app.after_request
    def response_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if response.mimetype == 'text/html':
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/health')
    def health():
        get_db().execute('SELECT 1 FROM users LIMIT 1').fetchone()
        return jsonify(status='ok', version='1.0.0')

    @app.get('/favicon.ico')
    def favicon():
        return '', 204

    from .cli import register_commands
    register_commands(app)
    return app
