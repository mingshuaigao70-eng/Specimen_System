from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
# login_view 在 create_app() 中统一设置，避免重复
csrf = CSRFProtect()