import logging
import os
import shutil
import time
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, redirect, render_template, request, url_for
from sqlalchemy import inspect

from config import Config

from .extensions import csrf, db, login_manager, migrate
from .models import PageContent, User
from .utils.password import generate_scrypt_hash
from .utils.time_utils import CHINA_TZ, format_time


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def _cleanup_temp_uploads(app):
    temp_dir = app.config.get('TEMP_UPLOAD_DIR')
    if not temp_dir or not os.path.isdir(temp_dir):
        return

    try:
        now_ts = time.time()
        for entry in os.listdir(temp_dir):
            entry_path = os.path.join(temp_dir, entry)
            if os.path.isdir(entry_path) and now_ts - os.path.getmtime(entry_path) > 7200:
                shutil.rmtree(entry_path, ignore_errors=True)
                app.logger.info('cleaned_expired_temp_dir name=%s', entry)
    except Exception:
        app.logger.exception('cleanup_temp_uploads_failed')


def _configure_logging(app):
    if app.debug:
        return

    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
    )
    file_handler.setFormatter(
        logging.Formatter(
            '%(asctime)s [%(levelname)s] %(module)s.%(funcName)s:%(lineno)d - %(message)s'
        )
    )
    file_handler.setLevel(logging.INFO)

    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('===== 应用启动 =====')


def _database_ready():
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    if not {'user', 'page_content'}.issubset(tables):
        return False

    page_content_columns = {column['name'] for column in inspector.get_columns('page_content')}
    return {'id', 'page', 'section', 'content', 'updated_by', 'created_at', 'updated_at'}.issubset(
        page_content_columns
    )


def _bootstrap_defaults(app):
    if not _database_ready():
        app.logger.warning(
            'database_tables_missing skip_bootstrap run="flask db upgrade" first'
        )
        return

    if not User.query.filter_by(role='superadmin').first():
        admin_pwd = os.environ.get('ADMIN_DEFAULT_PASSWORD', 'Admin123')
        default_admin = User(
            username='admin',
            password_hash=generate_scrypt_hash(admin_pwd),
            role='superadmin',
        )
        db.session.add(default_admin)
        db.session.commit()
        app.logger.info('default_superadmin_created username=admin')

    if PageContent.query.first():
        return

    defaults = [
        PageContent(page='landing', section='hero_title', content='黄河口水质水生态监测中心电子标本馆'),
        PageContent(page='landing', section='hero_subtitle', content='数字化标本管理与展示平台'),
        PageContent(page='landing', section='intro_heading', content='关于我们'),
        PageContent(
            page='landing',
            section='intro_text',
            content=(
                '黄河口水质水生态监测中心致力于黄河三角洲区域的水质与水生态监测工作，'
                '依托电子标本馆系统，实现对水生生物标本的数字化采集、管理、展示与共享，'
                '为科研、教育及生态保护提供数据支持。'
            ),
        ),
        PageContent(page='about', section='banner_title', content='关于我们'),
        PageContent(page='about', section='banner_subtitle', content='了解我们的工作与使命'),
        PageContent(page='about', section='content_heading', content='中心介绍'),
        PageContent(
            page='about',
            section='content_text',
            content=(
                '黄河口水质水生态监测中心位于黄河三角洲国家级自然保护区，长期开展黄河口及邻近海域的'
                '水环境质量监测、水生生物多样性调查与评价工作。\n\n'
                '中心配备先进的水质分析实验室和生物鉴定实验室，拥有一支专业的技术团队，在浮游生物、'
                '底栖动物、鱼类等水生生物类群的分类鉴定方面具有丰富经验。\n\n'
                '电子标本馆系统汇集了多年采集的水生生物标本信息，通过数字化手段实现标本信息的标准化存储、'
                '快速检索和在线展示，为黄河口流域的生态保护与管理提供科学依据。'
            ),
        ),
        PageContent(page='about', section='org_name', content='黄河口水质水生态监测中心'),
        PageContent(page='about', section='contact_person', content=''),
        PageContent(page='about', section='address', content=''),
        PageContent(page='about', section='postal_code', content=''),
        PageContent(page='about', section='email', content=''),
        PageContent(page='about', section='map_image', content=''),
        PageContent(page='site', section='footer_text', content='黄河口水质水生态监测中心 电子标本馆'),
    ]
    db.session.add_all(defaults)
    db.session.commit()
    app.logger.info('default_page_content_created count=%s', len(defaults))


def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
        static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static'),
    )
    app.config.from_object(Config)

    _cleanup_temp_uploads(app)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.session_protection = 'strong'
    csrf.init_app(app)

    @app.before_request
    def check_inactivity_timeout():
        from flask import session as flask_session
        from flask_login import current_user, logout_user

        if request.path.startswith('/auth/') or request.path.startswith('/static/'):
            return None

        if current_user.is_authenticated:
            timeout = app.config.get('INACTIVITY_TIMEOUT', timedelta(minutes=30))
            last_active = flask_session.get('_last_active')
            now = datetime.now(timezone.utc)
            if last_active:
                if isinstance(last_active, str):
                    last_active = datetime.fromisoformat(last_active)
                if now - last_active > timeout:
                    logout_user()
                    flask_session.clear()
                    return redirect(url_for('auth.login'))
            flask_session['_last_active'] = now.isoformat()
        return None

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get(
            'Accept', ''
        ).startswith('application/json'):
            return jsonify({'error': 'unauthorized', 'redirect': url_for('auth.login')}), 401
        return redirect(url_for('auth.login'))

    from .auth.routes import auth_bp
    from .main.routes import main_bp
    from .admin.routes import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if not app.debug:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.error('500 Internal Error: %s', error, exc_info=True)
        return render_template('errors/500.html'), 500

    @app.errorhandler(403)
    def forbidden(error):
        return render_template('errors/403.html'), 403

    @app.template_filter('datetime')
    def datetime_filter(value):
        return format_time(value)

    @app.template_filter('datetime_local')
    def datetime_local_filter(value):
        if not value:
            return ''
        if value.tzinfo is not None:
            value = value.astimezone(CHINA_TZ)
        else:
            value = CHINA_TZ.localize(value)
        return value.strftime('%Y-%m-%dT%H:%M')

    @app.template_filter('date_input')
    def date_input_filter(value):
        if not value:
            return ''
        if value.tzinfo is not None:
            value = value.astimezone(CHINA_TZ)
        else:
            value = CHINA_TZ.localize(value)
        return value.strftime('%Y-%m-%d')

    with app.app_context():
        _configure_logging(app)
        _bootstrap_defaults(app)

    return app
