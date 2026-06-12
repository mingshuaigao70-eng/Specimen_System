from flask import Flask, request
from .extensions import db, login_manager, csrf
from .models import User, PageContent
from config import Config
from .utils.password import generate_scrypt_hash
from .utils.time_utils import format_time  # 导入模板过滤器函数
import os
import shutil
import time
import logging
from logging.handlers import RotatingFileHandler

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

    # ---- 清理过期的临时上传目录（超过 2 小时的） ----
    temp_dir = app.config.get('TEMP_UPLOAD_DIR')
    if temp_dir and os.path.isdir(temp_dir):
        try:
            now_ts = time.time()
            for entry in os.listdir(temp_dir):
                entry_path = os.path.join(temp_dir, entry)
                if os.path.isdir(entry_path):
                    mtime = os.path.getmtime(entry_path)
                    if now_ts - mtime > 7200:  # 2 小时
                        shutil.rmtree(entry_path, ignore_errors=True)
                        app.logger.info(f'已清理过期临时目录: {entry}')
        except Exception:
            pass  # 启动时清理失败不影响服务

    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.session_protection = 'strong'

    # ========== 服务端无操作超时（30 分钟） ==========
    from datetime import datetime, timedelta, timezone

    @app.before_request
    def check_inactivity_timeout():
        """每次请求检查无操作超时，与浏览器会话 Cookie 配合：
        - Cookie 无 max-age → 关闭浏览器即删除 → 下次必须重登
        - 服务端 30 分钟无操作 → 主动清 session 踢出
        """
        from flask import session as flask_session, redirect, url_for
        from flask_login import current_user

        # 不拦截认证路由、静态文件和验证码
        if request.path.startswith('/auth/') or request.path.startswith('/static/'):
            return None

        if current_user.is_authenticated:
            timeout = app.config.get('INACTIVITY_TIMEOUT', timedelta(minutes=30))
            last_active = flask_session.get('_last_active')
            now = datetime.now(timezone.utc)
            if last_active:
                # Flask session 存的是字符串，需还原
                if isinstance(last_active, str):
                    last_active = datetime.fromisoformat(last_active)
                if now - last_active > timeout:
                    from flask_login import logout_user
                    logout_user()
                    flask_session.clear()
                    return redirect(url_for('auth.login'))
            # 更新最后活跃时间
            flask_session['_last_active'] = now.isoformat()

    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import request, jsonify, redirect, url_for
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
           request.headers.get('Accept', '').startswith('application/json'):
            return jsonify({'error': 'unauthorized', 'redirect': url_for('auth.login')}), 401
        return redirect(url_for('auth.login'))

    csrf.init_app(app)

    # 注册蓝图
    from .auth.routes import auth_bp
    from .main.routes import main_bp
    from .admin.routes import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    # ========== 安全响应头 ==========
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if not app.debug:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    # ========== 自定义错误页面 ==========
    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        app.logger.error(f'500 Internal Error: {e}', exc_info=True)
        from flask import render_template
        return render_template('errors/500.html'), 500

    @app.errorhandler(403)
    def forbidden(e):
        from flask import render_template
        return render_template('errors/403.html'), 403

    # 注册时间模板过滤器
    @app.template_filter('datetime')
    def datetime_filter(value):
        return format_time(value)

    @app.template_filter('datetime_local')
    def datetime_local_filter(value):
        if not value:
            return ''
        from .utils.time_utils import CHINA_TZ
        if value.tzinfo is not None:
            value = value.astimezone(CHINA_TZ)
        else:
            value = CHINA_TZ.localize(value)
        return value.strftime('%Y-%m-%dT%H:%M')

    @app.template_filter('date_input')
    def date_input_filter(value):
        if not value:
            return ''
        from .utils.time_utils import CHINA_TZ
        if value.tzinfo is not None:
            value = value.astimezone(CHINA_TZ)
        else:
            value = CHINA_TZ.localize(value)
        return value.strftime('%Y-%m-%d')

    # 创建默认超级管理员
    with app.app_context():
        db.create_all()  # 建表

        # ========== 日志配置 ==========
        if not app.debug:
            log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
            os.makedirs(log_dir, exist_ok=True)
            file_handler = RotatingFileHandler(
                os.path.join(log_dir, 'app.log'),
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=10
            )
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s [%(levelname)s] %(module)s.%(funcName)s:%(lineno)d — %(message)s'
            ))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)
            app.logger.setLevel(logging.INFO)
            app.logger.info('===== 应用启动 =====')

        if not User.query.filter_by(role='superadmin').first():
            admin_pwd = os.environ.get('ADMIN_DEFAULT_PASSWORD', 'Admin123')
            default_admin = User(
                username='admin',
                password_hash=generate_scrypt_hash(admin_pwd),
                role='superadmin'
            )
            db.session.add(default_admin)
            db.session.commit()
            app.logger.info('默认超级管理员 admin 已创建')

        # 初始化默认页面内容
        if not PageContent.query.first():
            defaults = [
                PageContent(page='landing', section='hero_title',
                            content='黄河口水质水生态监测中心电子标本馆'),
                PageContent(page='landing', section='hero_subtitle',
                            content='数字化标本管理与展示平台'),
                PageContent(page='landing', section='intro_heading',
                            content='关于我们'),
                PageContent(page='landing', section='intro_text',
                            content='黄河口水质水生态监测中心致力于黄河三角洲区域的水质与水生态监测工作，'
                                    '依托电子标本馆系统，实现对水生生物标本的数字化采集、管理、展示与共享，'
                                    '为科研、教育及生态保护提供数据支撑。'),
                PageContent(page='about', section='banner_title',
                            content='关于我们'),
                PageContent(page='about', section='banner_subtitle',
                            content='了解我们的工作与使命'),
                PageContent(page='about', section='content_heading',
                            content='中心介绍'),
                PageContent(page='about', section='content_text',
                            content='黄河口水质水生态监测中心位于黄河三角洲国家级自然保护区，'
                                    '长期开展黄河口及邻近海域的水环境质量监测、水生生物多样性调查与评价工作。'
                                    '\n\n中心配备先进的水质分析实验室和生物鉴定实验室，拥有一支专业的技术团队，'
                                    '在浮游生物、底栖动物、鱼类等水生生物类群的分类鉴定方面具有丰富经验。'
                                    '\n\n电子标本馆系统汇集了多年来采集的水生生物标本信息，通过数字化手段实现'
                                    '标本信息的标准化存储、快速检索和在线展示，为黄河口流域的生态保护与管理提供科学依据。'),
                # 关于我们 — 联系信息
                PageContent(page='about', section='org_name',
                            content='黄河口水质水生态监测中心'),
                PageContent(page='about', section='contact_person',
                            content=''),
                PageContent(page='about', section='address',
                            content=''),
                PageContent(page='about', section='postal_code',
                            content=''),
                PageContent(page='about', section='email',
                            content=''),
                PageContent(page='about', section='map_image',
                            content=''),
                PageContent(page='site', section='footer_text',
                            content='黄河口水质水生态监测中心 电子标本馆'),
            ]
            db.session.add_all(defaults)
            db.session.commit()
    return app