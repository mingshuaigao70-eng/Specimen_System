import os
from datetime import timedelta
from urllib.parse import quote_plus

# 加载 .env 文件（如果存在）
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
except ImportError:
    pass

basedir = os.path.dirname(os.path.abspath(__file__))


class Config:
    # ----- 安全密钥 -----
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        import warnings
        warnings.warn(
            '环境变量 SECRET_KEY 未设置！使用随机密钥（每次重启所有 session 将失效）。'
            '生产环境务必在 .env 文件中设置固定的 SECRET_KEY。',
            RuntimeWarning
        )
        SECRET_KEY = os.urandom(32).hex()

    # ----- MySQL 数据库配置 -----
    DB_USER = os.environ.get('DB_USER')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_NAME = os.environ.get('DB_NAME', 'specimen_db')
    if not DB_USER or not DB_PASSWORD:
        raise RuntimeError(
            '数据库凭据未配置。请设置环境变量 DB_USER 和 DB_PASSWORD，'
            '或创建 .env 文件并确保已安装 python-dotenv'
        )
    SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}@{DB_HOST}/{DB_NAME}?charset=utf8mb4'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ----- 数据库连接池 -----
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 20,
    }

    # ----- 调试模式 -----
    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

    # ----- Session 配置 -----
    # 无 PERMANENT_SESSION_LIFETIME — Cookie 为浏览器会话 Cookie，关闭浏览器即失效
    # 服务端 30 分钟无操作超时由 app/__init__.py 中的 before_request 钩子实现
    INACTIVITY_TIMEOUT = timedelta(minutes=30)
    REMEMBER_COOKIE_DURATION = timedelta(seconds=0)  # 禁止「记住我」— 关闭浏览器必须重登
    SESSION_REFRESH_EACH_REQUEST = True
    # 本地开发使用 adhoc SSL 时 Secure 设为 False，生产必须为 True
    SESSION_COOKIE_SECURE = not DEBUG
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # ----- CSRF 配置 -----
    WTF_CSRF_ENABLED = True
    # 本地开发时放宽 Referer 检查（adhoc SSL 可能无 Referer）
    WTF_CSRF_SSL_STRICT = not DEBUG

    # ----- 上传目录 -----
    UPLOAD_FOLDER_IMAGES = os.path.join(basedir, 'static/images')
    UPLOAD_FOLDER_SPECIMEN_IMAGES = os.path.join(basedir, 'static/images/specimens')
    UPLOAD_FOLDER_CATEGORY_IMAGES = os.path.join(basedir, 'static/images/public')

    # ----- 文件上传限制 -----
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 最大上传 100 MB（支持批量 ZIP）
    MAX_IMAGE_SIZE = 1 * 1024 * 1024        # 单张图片最大 1 MB
    MAX_ZIP_SIZE = 100 * 1024 * 1024        # ZIP 批量上传包最大 100 MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

    # ----- 批量上传临时目录 -----
    TEMP_UPLOAD_DIR = os.path.join(basedir, 'temp_uploads')