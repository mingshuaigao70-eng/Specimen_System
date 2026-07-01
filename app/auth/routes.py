import time

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..models import User
from ..utils.password import verify_scrypt_hash
from ..utils.verify_code import generate_captcha

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/captcha')
def captcha():
    code, image = generate_captcha()
    session['captcha_code'] = code.lower()
    session['captcha_time'] = time.time()
    return send_file(image, mimetype='image/png')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        captcha_input = request.form.get('captcha', '').lower()

        now = time.time()
        attempts = session.get('login_attempts', [])
        attempts = [t for t in attempts if now - t < 60]
        if len(attempts) >= 5:
            remaining = int(60 - (now - attempts[0]))
            current_app.logger.warning('login_rate_limited username=%s ip=%s', username, request.remote_addr)
            flash(f'登录过于频繁，请 {remaining} 秒后再试')
            return render_template('login.html')
        attempts.append(now)
        session['login_attempts'] = attempts

        captcha_time = session.get('captcha_time', 0)
        stored_code = session.get('captcha_code', '')
        session.pop('captcha_code', None)
        session.pop('captcha_time', None)

        if now - captcha_time > 300 or captcha_input != stored_code:
            current_app.logger.warning('captcha_validation_failed username=%s ip=%s', username, request.remote_addr)
            flash('验证码错误或已过期，请刷新验证码')
            return render_template('login.html')

        user = User.query.filter_by(username=username).first()
        if user and verify_scrypt_hash(password, user.password_hash):
            session.pop('login_attempts', None)
            login_user(user)
            current_app.logger.info('login_success username=%s role=%s ip=%s', user.username, user.role, request.remote_addr)
            return redirect(url_for('main.index'))

        current_app.logger.warning('login_failed username=%s ip=%s', username, request.remote_addr)
        flash('用户名或密码错误')
    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    current_app.logger.info('logout username=%s ip=%s', current_user.username, request.remote_addr)
    logout_user()
    session.clear()
    return redirect(url_for('auth.login'))
