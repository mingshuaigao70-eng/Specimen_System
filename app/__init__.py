# app/__init__.py
from flask import Flask
from .extensions import db, login_manager
from .models import User
from sqlalchemy import create_engine
from sqlalchemy_utils import database_exists, create_database
from config import Config
from .utils.password import generate_scrypt_hash
import  os

# user_loader 回调
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
def create_app():
    # 指定模板路径和静态文件路径
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
        static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    )
    app.config.from_object(Config)

    # 自动创建数据库
    uri = app.config['SQLALCHEMY_DATABASE_URI']
    engine_url = uri.rsplit('/', 1)[0]
    engine = create_engine(engine_url)
    if not database_exists(uri):
        create_database(uri)
        print("数据库创建完成！")

    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # 蓝图注册
    from .auth.routes import auth_bp
    from .main.routes import main_bp
    from .admin.routes import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    # 首次建表 + 默认管理员
    with app.app_context():
        db.create_all()
        print("数据库表创建完成！")
        if not User.query.filter_by(is_admin=True).first():
            default_admin = User(
                username='admin',
                password_hash=generate_scrypt_hash('Admin123'),
                is_admin=True
            )
            db.session.add(default_admin)
            db.session.commit()
            print("默认管理员 admin 已创建，密码：Admin123")

    return app