"""Phone authentication; SMS_SENDER(phone, code) supplies production delivery."""
import hashlib
import hmac
import re
import secrets
import time
from datetime import datetime

from flask import Blueprint, current_app as app, jsonify, render_template, request, session
from flask import redirect, flash
from werkzeug.security import generate_password_hash
from .db import get_db, IntegrityErrors
from .security import safe_next

bp = Blueprint('phone_auth', __name__)


@bp.after_request
def prevent_caching(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


def digest(phone, purpose, code):
    return hmac.new(app.secret_key.encode(), f'{phone}:{purpose}:{code}'.encode(), hashlib.sha256).hexdigest()


def demo_enabled():
    return app.config['SMS_DEMO'] and not app.config['PRODUCTION']


@bp.post('/auth/sms/send')
def send_code():
    phone = request.form.get('phone', '').strip()
    purpose = request.form.get('purpose', '')
    if not re.fullmatch(r'1[3-9][0-9]{9}', phone) or purpose not in ('login', 'register'):
        return jsonify(message='请输入有效的中国大陆手机号和验证码用途'), 400
    if not demo_enabled() and not callable(app.config.get('SMS_SENDER')):
        return jsonify(message='短信服务尚未配置，请联系管理员'), 503
    db = get_db()
    now = time.time()
    # Fixed-window counters are shared by workers, with atomic capped increments.
    keys = [(f'phone-minute:{phone}:{int(now // 60)}', 1),
            (f'phone-hour:{phone}:{int(now // 3600)}', 10),
            (f'ip-hour:{request.remote_addr}:{int(now // 3600)}', 30)]
    db.execute('DELETE FROM sms_limits WHERE expires_at < ?', (now,))
    for raw, limit in keys:
        key = hashlib.sha256(raw.encode()).hexdigest()
        db.execute('INSERT OR IGNORE INTO sms_limits(identity,hits,expires_at) VALUES (?,0,?)', (key, now + 3600))
        result = db.execute('UPDATE sms_limits SET hits=hits+1 WHERE identity=? AND hits < ?', (key, limit))
        if result.rowcount != 1:
            db.rollback()
            return jsonify(message='验证码发送过于频繁，请稍后重试'), 429
    previous = db.execute('SELECT sent_at FROM sms_codes WHERE phone=? ORDER BY sent_at DESC LIMIT 1', (phone,)).fetchone()
    if previous and now - previous['sent_at'] < 60:
        db.rollback()
        return jsonify(message='请在60秒后重新获取验证码'), 429
    code = f'{secrets.randbelow(1000000):06d}'
    db.execute('''INSERT INTO sms_codes(phone,purpose,code_hash,expires_at,attempts,sent_at)
        VALUES (?,?,?,?,0,?) ON CONFLICT(phone,purpose) DO UPDATE SET
        code_hash=excluded.code_hash,expires_at=excluded.expires_at,attempts=0,sent_at=excluded.sent_at''',
        (phone, purpose, digest(phone, purpose, code), now + 300, now))
    db.commit()
    if not demo_enabled():
        try:
            app.config['SMS_SENDER'](phone, code)
        except Exception:
            db.execute('DELETE FROM sms_codes WHERE phone=? AND purpose=? AND code_hash=?',
                       (phone, purpose, digest(phone, purpose, code)))
            db.commit()
            return jsonify(message='短信发送失败，请稍后重试'), 503
    response = dict(message='验证码已发送，5分钟内有效', retry_after=60)
    if demo_enabled():
        response.update(message='演示模式：未发送真实短信', demo_code=code)
    return jsonify(response)


@bp.route('/phone/<purpose>', methods=['GET', 'POST'])
def authenticate(purpose):
    if purpose not in ('login', 'register'):
        from flask import abort
        abort(404)
    if request.method == 'GET':
        return render_template('phone_auth.html', mode=purpose, sms_demo=demo_enabled())
    phone = request.form.get('phone', '').strip()
    code = request.form.get('code', '').strip()
    db = get_db()
    if not re.fullmatch(r'1[3-9][0-9]{9}', phone) or not re.fullmatch(r'[0-9]{6}', code):
        flash('请输入有效手机号和6位验证码', 'error')
        return render_template('phone_auth.html', mode=purpose, sms_demo=demo_enabled()), 400
    db.execute('UPDATE sms_codes SET attempts=attempts+1 WHERE phone=? AND purpose=?', (phone, purpose))
    consumed = db.execute('''DELETE FROM sms_codes WHERE phone=? AND purpose=? AND code_hash=?
        AND expires_at > ? AND attempts <= 5''', (phone, purpose, digest(phone, purpose, code), time.time()))
    db.commit()
    if consumed.rowcount != 1:
        flash('验证码错误、已过期或尝试次数过多，请重新获取', 'error')
        return render_template('phone_auth.html', mode=purpose, sms_demo=demo_enabled()), 400
    user = db.execute('SELECT u.* FROM users u JOIN phone_accounts p ON p.user_id=u.id WHERE p.phone=?', (phone,)).fetchone()
    if purpose == 'register' and user:
        flash('该手机号已注册，请使用手机验证码登录', 'error')
    elif purpose == 'login' and not user:
        flash('该手机号尚未注册，请先注册', 'error')
    elif user and not user['is_active']:
        flash('账号已停用', 'error')
    else:
        if not user:
            try:
                username = '手机用户_' + secrets.token_hex(5)
                result = db.execute('INSERT INTO users(username,password_hash,created_at) VALUES (?,?,?)',
                                    (username, generate_password_hash(secrets.token_urlsafe(32)), datetime.now().isoformat(timespec='seconds')))
                db.execute('INSERT INTO phone_accounts(phone,user_id) VALUES (?,?)', (phone, result.lastrowid))
                db.commit()
                user = db.execute('SELECT * FROM users WHERE id=?', (result.lastrowid,)).fetchone()
            except IntegrityErrors:
                db.rollback()
                flash('手机号已注册，请重新获取验证码登录', 'error')
                return render_template('phone_auth.html', mode=purpose, sms_demo=demo_enabled()), 400
        session.clear()
        session.update(user_id=user['id'], version=user['session_version'])
        flash('注册成功' if purpose == 'register' else '登录成功', 'success')
        return redirect(safe_next())
    return render_template('phone_auth.html', mode=purpose, sms_demo=demo_enabled()), 400
