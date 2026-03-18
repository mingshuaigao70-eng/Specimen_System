import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here')

    # MySQL 数据库配置（修改用户名、密码、数据库名）
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:gms980923%40@localhost/specimen_db?charset=utf8mb4'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 上传目录
    UPLOAD_FOLDER_IMAGES = os.path.join(os.getcwd(), 'static/images')
    UPLOAD_FOLDER_QR = os.path.join(os.getcwd(), 'static/qrcodes')

    # 文件上传限制
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 最大上传16MB
    MAX_IMAGE_SIZE = 1 * 1024 * 1024      # 单张图片最大1MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}