from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file
from flask_login import login_user, login_required, logout_user
from ..models import User
from ..utils.password import verify_scrypt_hash
from ..utils.verify_code import generate_captcha

auth_bp = Blueprint('auth', __name__)

# 生成验证码
@auth_bp.route('/captcha')
def captcha():
    code, image = generate_captcha()
    session['captcha_code'] = code.lower()  # 保存小写形式
    return send_file(image, mimetype='image/png')

# 登录
@auth_bp.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        captcha_input = request.form.get('captcha', '').lower()

        # 验证验证码
        if captcha_input != session.get('captcha_code', ''):
            flash("验证码错误")
            return render_template('login.html')

        user = User.query.filter_by(username=username).first()
        if user and verify_scrypt_hash(password, user.password_hash):
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
    return redirect(url_for('auth.login'))