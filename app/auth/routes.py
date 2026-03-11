from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from app.models import User
from app.extensions import db
from app.auth.forms import LoginForm, RegisterForm
from app.utils.password import generate_scrypt_hash, check_scrypt_hash

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_scrypt_hash(user.password_hash, form.password.data):
            login_user(user)
            flash("登录成功！")
            return redirect(url_for('main.index'))
        else:
            flash("用户名或密码错误")
    return render_template('login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if form.password.data != form.confirm_password.data:
            flash("两次密码不一致")
            return redirect(url_for('auth.register'))
        if User.query.filter_by(username=form.username.data).first():
            flash("用户名已存在")
            return redirect(url_for('auth.register'))
        user = User(username=form.username.data,
                    password_hash=generate_scrypt_hash(form.password.data))
        db.session.add(user)
        db.session.commit()
        flash("注册成功！请登录")
        return redirect(url_for('auth.login'))
    return render_template('register.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("已退出登录")
    return redirect(url_for('main.index'))