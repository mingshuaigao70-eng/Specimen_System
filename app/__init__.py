from flask import Flask
from .extensions import db, login_manager
from .models import User
from config import Config
from .utils.password import generate_scrypt_hash
from .utils.time_utils import format_time  # 导入模板过滤器函数
import os

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
        static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    )
    app.config.from_object(Config)
    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # 注册蓝图
    from .auth.routes import auth_bp
    from .main.routes import main_bp
    from .admin.routes import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    # 注册时间模板过滤器
    @app.template_filter('datetime')
    def datetime_filter(value):
        return format_time(value)

    # 创建默认超级管理员
    with app.app_context():
        db.create_all()  # 建表
        if not User.query.filter_by(role='superadmin').first():
            default_admin = User(
                username='admin',
                password_hash=generate_scrypt_hash('Admin123'),
                role='superadmin'
            )
            db.session.add(default_admin)
            db.session.commit()
            print("默认超级管理员 admin 已创建，密码：Admin123")
    return app