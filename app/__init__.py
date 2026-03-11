from flask import Flask
from .extensions import db, login_manager
from .main.routes import main_bp
from .models import User
from .utils.password import generate_scrypt_hash
def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config['SECRET_KEY'] = 'your-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'

    # 用户加载器
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # 注册蓝图
    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()

        # 创建默认管理员用户
        if not User.query.filter_by(username='admin').first():
            hashed_pw = generate_scrypt_hash('Admin123')  # 先加密密码
            default_user = User(username='admin', password_hash=hashed_pw)
            db.session.add(default_user)
            db.session.commit()

    return app