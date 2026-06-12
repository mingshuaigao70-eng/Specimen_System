from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file
from flask_login import login_user, login_required, logout_user
from ..models import User
from ..utils.password import verify_scrypt_hash
from ..utils.verify_code import generate_captcha
import time

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# 生成验证码
@auth_bp.route('/captcha')
def captcha():
    code, image = generate_captcha()
    session['captcha_code'] = code.lower()  # 保存小写形式
    session['captcha_time'] = time.time()   # 记录生成时间
    return send_file(image, mimetype='image/png')

# 登录
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        captcha_input = request.form.get('captcha', '').lower()

        # ===== 登录频率限制：1 分钟内最多 5 次 =====
        now = time.time()
        attempts = session.get('login_attempts', [])
        # 清理 60 秒前的记录
        attempts = [t for t in attempts if now - t < 60]
        if len(attempts) >= 5:
            remaining = int(60 - (now - attempts[0]))
            flash(f'登录过于频繁，请 {remaining} 秒后再试')
            return render_template('login.html')
        attempts.append(now)
        session['login_attempts'] = attempts

        # ===== 验证码校验（5 分钟过期）=====
        captcha_time = session.get('captcha_time', 0)
        stored_code = session.get('captcha_code', '')
        # 用完立即清除，防止重放
        session.pop('captcha_code', None)
        session.pop('captcha_time', None)

        if now - captcha_time > 300 or captcha_input != stored_code:
            flash("验证码错误或已过期，请刷新验证码")
            return render_template('login.html')

        user = User.query.filter_by(username=username).first()
        if user and verify_scrypt_hash(password, user.password_hash):
            session.pop('login_attempts', None)  # 登录成功清除尝试记录
            login_user(user)
            return redirect(url_for('main.index'))
        else:
            flash("用户名或密码错误")
    return render_template('login.html')

# 退出登录
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('auth.login'))