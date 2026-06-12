from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app, session, jsonify
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
from ..extensions import db
from ..models import User, Specimen, SpecimenImage, SpecimenCategory, PageContent
from ..utils.password import generate_scrypt_hash
from app.utils.file_util import FileHandler
from app.utils.excel_util import parse_workbook, extract_code_from_number
import json
import os
import re
import uuid
import zipfile
import shutil
from io import BytesIO
from sqlalchemy.exc import IntegrityError
from app.utils.time_utils import now , CHINA_TZ
from ..utils.search_utils import build_specimen_search_filter

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# -------------------- 权限装饰器 -------------------- #
def superadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role != 'superadmin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ['superadmin', 'admin']:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# -------------------- 安全表单解析工具 -------------------- #
def _parse_datetime_form_value(value_str, default=None):
    """安全解析表单中的日期时间值，格式错误时返回 default 而非崩溃"""
    if not value_str:
        return default
    try:
        fmt = "%Y-%m-%dT%H:%M" if 'T' in value_str else "%Y-%m-%d"
        dt = datetime.strptime(value_str, fmt)
        return CHINA_TZ.localize(dt)
    except (ValueError, TypeError):
        return default


def _parse_float_form_value(value_str, default=None):
    """安全解析表单中的浮点数值，格式错误时返回 default 而非崩溃"""
    if not value_str or not str(value_str).strip():
        return default
    try:
        return float(value_str)
    except (ValueError, TypeError):
        return default


def _parse_int_form_value(value_str, default=None):
    """安全解析表单中的整数值，格式错误时返回 default 而非崩溃"""
    if not value_str or not str(value_str).strip():
        return default
    try:
        return int(value_str)
    except (ValueError, TypeError):
        return default


# -------------------- 平台首页 -------------------- #
@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    default_url = '/users' if current_user.role == 'superadmin' else '/specimens'
    return render_template('admin/admin_dashboard.html', default_url=default_url)

# -------------------- 页面配置 -------------------- #
@admin_bp.route('/page_config', methods=['GET', 'POST'])
@login_required
@superadmin_required
def page_config():
    if request.method == 'POST':
        rows = PageContent.query.all()
        row_map = {f'{r.page}.{r.section}': r for r in rows}
        for key in request.form:
            if key in row_map:
                row_map[key].content = request.form[key]
                row_map[key].updated_by = current_user.username
                row_map[key].updated_at = datetime.now()

        # 处理首页横幅背景图上传
        image_file = request.files.get('banner_image')
        if image_file and FileHandler.check_file(image_file):
            try:
                ext = image_file.filename.rsplit('.', 1)[1].lower()
                filename = f"banner.{ext}"
                # 删除旧横幅图片
                old = PageContent.query.filter_by(page='landing', section='banner_image').first()
                if old and old.content:
                    old_path = os.path.join(current_app.config['UPLOAD_FOLDER_CATEGORY_IMAGES'], os.path.basename(old.content))
                    if os.path.exists(old_path):
                        os.remove(old_path)
                relative_path = FileHandler.save_file(image_file, folder_key='UPLOAD_FOLDER_CATEGORY_IMAGES', filename=filename)
                if old:
                    old.content = relative_path
                    old.updated_by = current_user.username
                    old.updated_at = datetime.now()
                else:
                    db.session.add(PageContent(
                        page='landing', section='banner_image',
                        content=relative_path,
                        updated_by=current_user.username
                    ))
            except IOError as e:
                flash(f'横幅图片保存失败: {e}', 'error')
                return redirect(url_for('admin.page_config'))

        # 处理关于我们页面地图图片上传
        map_file = request.files.get('map_image')
        if map_file and FileHandler.check_file(map_file):
            try:
                ext = map_file.filename.rsplit('.', 1)[1].lower()
                filename = f"map.{ext}"
                old = PageContent.query.filter_by(page='about', section='map_image').first()
                if old and old.content:
                    old_path = os.path.join(current_app.config['UPLOAD_FOLDER_CATEGORY_IMAGES'], os.path.basename(old.content))
                    if os.path.exists(old_path):
                        os.remove(old_path)
                relative_path = FileHandler.save_file(map_file, folder_key='UPLOAD_FOLDER_CATEGORY_IMAGES', filename=filename)
                if old:
                    old.content = relative_path
                    old.updated_by = current_user.username
                    old.updated_at = datetime.now()
                else:
                    db.session.add(PageContent(
                        page='about', section='map_image',
                        content=relative_path,
                        updated_by=current_user.username
                    ))
            except IOError as e:
                flash(f'地图图片保存失败: {e}', 'error')
                return redirect(url_for('admin.page_config'))

        db.session.commit()
        flash('页面内容已更新', 'success')
        return redirect(url_for('admin.page_config'))

    rows = PageContent.query.all()
    content = {f'{r.page}.{r.section}': r.content for r in rows}
    return render_template('admin/admin_page_config.html', content=content)

# ==================== 用户管理 ==================== #

ALLOWED_ROLES = ('admin', 'user')  # superadmin 不允许通过 Web 界面分配

# 常见弱密码黑名单 — 均满足密码强度规则但极易被猜测
COMMON_WEAK_PASSWORDS = {
    'Password1!', 'Admin123!', 'Admin123!@#', 'admin123!@#',
    'Qwerty1!', 'Qwerty123!', 'Welcome1!', 'Welcome123!',
    'Changeme1!', 'P@ssw0rd1', 'Pa$$w0rd1', 'Abcd1234!',
    'ABCabc123!', 'Passw0rd!', 'Passw0rd1!',
}


def _validate_password(password):
    """校验密码强度，返回 (is_valid, error_message)"""
    if len(password) < 8:
        return False, '密码至少 8 位！'
    if not (any(c.islower() for c in password) and
            any(c.isupper() for c in password) and
            any(c.isdigit() for c in password) and
            any(not c.isalnum() for c in password)):
        return False, '密码需包含大写字母、小写字母、数字、特殊字符！'
    if password in COMMON_WEAK_PASSWORDS:
        return False, '密码过于常见，请使用更复杂的密码！'
    return True, None


@admin_bp.route('/users')
@login_required
@superadmin_required
def manage_users():
    users = User.query.all()
    return render_template('admin/admin_user_management.html', users=users)

@admin_bp.route('/users/add', methods=['GET', 'POST'])
@login_required
@superadmin_required
def add_user():
    if request.method == 'POST':
        username = request.form['username'].strip()
        role = request.form['role']
        password = request.form['password']

        if role not in ALLOWED_ROLES:
            flash('无效的角色值', 'error')
            return redirect(url_for('admin.add_user'))

        if User.query.filter_by(username=username).first():
            flash('用户名已存在！', 'error')
            return redirect(url_for('admin.add_user'))

        # 密码强度校验
        valid, err = _validate_password(password)
        if not valid:
            flash(err, 'error')
            return redirect(url_for('admin.add_user'))

        new_user = User(
            username=username,
            role=role,
            password_hash=generate_scrypt_hash(password)
        )
        db.session.add(new_user)
        db.session.commit()
        flash('新增用户成功！', 'success')
        return redirect(url_for('admin.manage_users'))
    return render_template('admin/admin_add_user.html')


@admin_bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@superadmin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        # ── 超级管理员账号仅支持修改密码 ──
        if user.role == 'superadmin':
            password = request.form.get('password', '').strip()
            if not password:
                flash('请输入新密码', 'error')
                return redirect(url_for('admin.manage_users'))
            valid, err = _validate_password(password)
            if not valid:
                flash(err, 'error')
                return redirect(url_for('admin.manage_users'))
            user.password_hash = generate_scrypt_hash(password)
            db.session.commit()
            flash('密码已更新！', 'success')
            return redirect(url_for('admin.manage_users'))

        # ── 非超级管理员：可修改用户名、角色，密码可选 ──
        new_username = request.form.get('username', '').strip()
        new_role = request.form.get('role', 'user')
        if new_role not in ALLOWED_ROLES:
            flash('无效的角色值', 'error')
            return redirect(url_for('admin.manage_users'))

        existing = User.query.filter(User.username == new_username, User.id != user_id).first()
        if existing:
            flash('用户名已存在！', 'error')
            return redirect(url_for('admin.manage_users'))

        user.username = new_username
        user.role = new_role

        password = request.form.get('password', '').strip()
        if password:
            valid, err = _validate_password(password)
            if not valid:
                flash(err, 'error')
                return redirect(url_for('admin.manage_users'))
            user.password_hash = generate_scrypt_hash(password)

        db.session.commit()
        flash('用户信息已更新！', 'success')
        return redirect(url_for('admin.manage_users'))
    return render_template('admin/admin_edit_user.html', user=user)

@admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@superadmin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.username == 'admin':
        flash('默认超级管理员不可删除', 'error')
        return redirect(url_for('admin.manage_users'))
    db.session.delete(user)
    db.session.commit()
    flash('用户已删除！', 'success')
    return redirect(url_for('admin.manage_users'))

# ------------------- 标本大类管理 ------------------- #
# 列表展示
@admin_bp.route('/categories')
@login_required
@admin_required
def list_categories():
    categories = SpecimenCategory.query.order_by(SpecimenCategory.id.desc()).all()
    return render_template('admin/admin_category_management.html', categories=categories)

# 新增大类
@admin_bp.route('/categories/add', methods=['POST'])
@login_required
@admin_required
def add_category():
    name = request.form.get('name')
    code = request.form.get('code')
    description = request.form.get('description')
    if not name:
        flash('类别名称不能为空', 'warning')
        return redirect(url_for('admin.list_categories'))
    if not code:
        flash('唯一性代码不能为空', 'warning')
        return redirect(url_for('admin.list_categories'))

    if SpecimenCategory.query.filter_by(name=name).first():
        flash('该类别已存在', 'warning')
        return redirect(url_for('admin.list_categories'))
    if SpecimenCategory.query.filter_by(code=code).first():
        flash('该唯一性代码已存在', 'warning')
        return redirect(url_for('admin.list_categories'))

    category = SpecimenCategory(
        name=name,
        code=code,
        description=description,
        created_by=current_user.username,
        updated_by=current_user.username,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

    # 处理封面图片上传
    image_file = request.files.get('image')
    if image_file and FileHandler.check_file(image_file):
        try:
            ext = image_file.filename.rsplit('.', 1)[1].lower()
            filename = f"{name}.{ext}"
            relative_path = FileHandler.save_file(image_file, folder_key='UPLOAD_FOLDER_CATEGORY_IMAGES', filename=filename)
            category.image = relative_path
        except IOError as e:
            flash(f'封面图片保存失败: {e}', 'error')
            return redirect(url_for('admin.list_categories'))

    db.session.add(category)
    db.session.commit()
    flash('大类添加成功', 'success')
    return redirect(url_for('admin.list_categories'))

# 编辑大类
# 编辑大类（仅POST）
@admin_bp.route('/categories/edit/<int:id>', methods=['POST'])
@login_required
@admin_required
def edit_category(id):
    category = SpecimenCategory.query.get_or_404(id)
    new_name = request.form.get('name')
    new_code = request.form.get('code')
    description = request.form.get('description')
    if not new_name:
        flash('类别名称不能为空', 'warning')
        return redirect(url_for('admin.list_categories'))
    if not new_code:
        flash('唯一性代码不能为空', 'warning')
        return redirect(url_for('admin.list_categories'))

    # 检查是否重复
    exists = SpecimenCategory.query.filter(
        SpecimenCategory.name == new_name,
        SpecimenCategory.id != id
    ).first()
    if exists:
        flash('该类别名称已存在', 'warning')
        return redirect(url_for('admin.list_categories'))
    code_exists = SpecimenCategory.query.filter(
        SpecimenCategory.code == new_code,
        SpecimenCategory.id != id
    ).first()
    if code_exists:
        flash('该唯一性代码已存在', 'warning')
        return redirect(url_for('admin.list_categories'))

    category.name = new_name
    category.code = new_code
    category.description = description
    category.updated_by = current_user.username
    category.updated_at = datetime.now()

    # 处理封面图片上传（替换旧图）
    image_file = request.files.get('image')
    if image_file and FileHandler.check_file(image_file):
        try:
            # 删除旧图片
            if category.image:
                old_path = os.path.join(current_app.config['UPLOAD_FOLDER_CATEGORY_IMAGES'], os.path.basename(category.image))
                if os.path.exists(old_path):
                    os.remove(old_path)
            ext = image_file.filename.rsplit('.', 1)[1].lower()
            filename = f"{new_name}.{ext}"
            relative_path = FileHandler.save_file(image_file, folder_key='UPLOAD_FOLDER_CATEGORY_IMAGES', filename=filename)
            category.image = relative_path
        except IOError as e:
            flash(f'封面图片保存失败: {e}', 'error')
            return redirect(url_for('admin.list_categories'))

    db.session.commit()
    flash('大类修改成功', 'success')
    return redirect(url_for('admin.list_categories'))

# 删除大类
@admin_bp.route('/categories/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_category(id):
    category = SpecimenCategory.query.get_or_404(id)
    if category.specimens:  # 如果有关联标本
        flash('该大类下还有标本，无法删除', 'danger')
        return redirect(url_for('admin.list_categories'))
    # 删除封面图片文件
    if category.image:
        img_path = os.path.join(current_app.config['UPLOAD_FOLDER_CATEGORY_IMAGES'], os.path.basename(category.image))
        if os.path.exists(img_path):
            os.remove(img_path)
    db.session.delete(category)
    db.session.commit()
    flash('大类删除成功', 'success')
    return redirect(url_for('admin.list_categories'))

# ==================== 标本信息维护 ==================== #
@admin_bp.route('/specimens')
@login_required
@admin_required
def manage_specimens():
    category_id = request.args.get('category_id', type=int)
    q = request.args.get('q', '').strip()
    categories = SpecimenCategory.query.all()

    query = Specimen.query
    if category_id:
        query = query.filter_by(category_id=category_id)
    if q:
        search_filter = build_specimen_search_filter(q)
        if search_filter is not None:
            query = query.filter(search_filter)

    page = request.args.get('page', 1, type=int)
    per_page = 30
    pagination = query.order_by(Specimen.id.desc()) \
        .paginate(page=page, per_page=per_page, error_out=False)
    specimens = pagination.items

    # 构建标本 JSON 数据，供编辑模态框使用
    def fmt_dt(dt_val):
        if not dt_val:
            return ''
        from app.utils.time_utils import CHINA_TZ
        if dt_val.tzinfo is not None:
            dt_val = dt_val.astimezone(CHINA_TZ)
        else:
            dt_val = CHINA_TZ.localize(dt_val)
        return dt_val.strftime('%Y-%m-%dT%H:%M')

    specimens_json = {}
    for s in specimens:
        specimens_json[str(s.id)] = {
            'id': s.id,
            'category_id': s.category_id,
            'specimen_number': s.specimen_number,
            'chinese_name': s.chinese_name or '',
            'latin_name': s.latin_name or '',
            'alias': s.alias or '',
            'phylum': s.phylum or '',
            'class_name': s.class_name or '',
            'order_name': s.order_name or '',
            'family': s.family or '',
            'genus': s.genus or '',
            'species': s.species or '',
            'collector': s.collector or '',
            'collect_time': fmt_dt(s.collect_time),
            'collect_location': s.collect_location or '',
            'longitude': float(s.longitude) if s.longitude is not None else None,
            'latitude': float(s.latitude) if s.latitude is not None else None,
            'appraiser': s.appraiser or '',
            'appraisal_time': fmt_dt(s.appraisal_time),
            'other_info': s.other_info if isinstance(s.other_info, str) else (json.dumps(s.other_info, ensure_ascii=False) if s.other_info else None),
            'images': [{'id': img.id, 'url': url_for('static', filename=img.image_path)}
                       for img in s.images]
        }

    return render_template('admin/admin_specimen_management.html',
                           specimens=specimens,
                           specimens_json=specimens_json,
                           categories=categories,
                           current_category_id=category_id,
                           search_query=q,
                           pagination=pagination)

# ==================== 上传标本 ===================== #
@admin_bp.route('/upload_specimen', methods=['GET', 'POST'])
@login_required
@admin_required
def upload_specimen():
    if request.method == 'POST':
        # ==================== 获取表单数据 ==================== #
        category_id = request.form.get('category_id')  # 标本大类 ID
        specimen_number = request.form.get('specimen_number')  # 标本编号
        chinese_name = request.form.get('chinese_name') or None
        latin_name = request.form.get('latin_name')
        alias = request.form.get('alias') or None
        phylum = request.form.get('phylum') or None
        class_name = request.form.get('class_name') or None
        order_name = request.form.get('order') or None
        family = request.form.get('family') or None
        genus = request.form.get('genus') or None
        species = request.form.get('species') or None
        collector = request.form.get('collector') or None

        # ---- 必填字段验证（门/纲/目/科/属） ----
        required_fields = [
            ('phylum', '门'),
            ('class_name', '纲'),
            ('order', '目'),
            ('family', '科'),
            ('genus', '属'),
        ]
        missing = []
        for field_name, label in required_fields:
            val = (request.form.get(field_name) or '').strip()
            if not val:
                missing.append(label)
        if missing:
            flash(f"以下必填字段不能为空：{'、'.join(missing)}", 'error')
            return redirect(url_for('admin.upload_specimen'))

        # ---- 标本编号非空 + 唯一性检查 ----
        if not specimen_number or not specimen_number.strip():
            flash("标本编号不能为空", 'error')
            return redirect(url_for('admin.upload_specimen'))

        existing = Specimen.query.filter_by(specimen_number=specimen_number.strip()).first()
        if existing:
            flash(f"标本编号 '{specimen_number}' 已存在，请使用其他编号", 'error')
            return redirect(url_for('admin.upload_specimen'))

        # 采集时间（兼容 date 和 datetime-local 两种格式）
        collect_time = _parse_datetime_form_value(request.form.get('collect_time'), default=now())

        collect_location = request.form.get('collect_location') or None

        # ==================== 经纬度处理 ==================== #
        longitude = _parse_float_form_value(request.form.get('longitude'))
        latitude = _parse_float_form_value(request.form.get('latitude'))

        # ==================== 鉴定信息 ==================== #
        appraiser = request.form.get('appraiser') or None
        appraisal_time = _parse_datetime_form_value(request.form.get('appraisal_time'))

        # ==================== 其他信息（JSON 或文本） ==================== #
        other_info = request.form.get('other_info')
        try:
            other_info_json = json.loads(other_info) if other_info else None
        except Exception:
            other_info_json = other_info or None

        # ==================== 创建 Specimen 实例 ==================== #
        category_id_int = _parse_int_form_value(category_id)
        if category_id_int is None:
            flash("请选择有效的标本大类", 'error')
            return redirect(url_for('admin.upload_specimen'))
        specimen = Specimen(
            category_id=category_id_int,
            specimen_number=specimen_number,
            chinese_name=chinese_name,
            latin_name=latin_name,
            alias=alias,
            phylum=phylum,
            class_name=class_name,
            order_name=order_name,
            family=family,
            genus=genus,
            species=species,
            collector=collector,
            collect_time=collect_time,
            collect_location=collect_location,
            longitude=longitude,
            latitude=latitude,
            appraiser=appraiser,
            appraisal_time=appraisal_time,
            other_info=other_info_json,
            created_by=current_user.username,
            updated_by=current_user.username,
            # ⚠️ 不再手动传 created_at/updated_at，使用模型默认 now()
        )
        db.session.add(specimen)
        db.session.flush()  # 先获取 specimen.id，尚未提交事务

        # ==================== 处理多张图片（以标本号命名） ==================== #
        images = request.files.getlist('images')
        safe_number = re.sub(r'[\\/:*?"<>|]', '_', specimen_number)
        saved_files = []  # 跟踪已保存的文件路径，commit 失败时清理
        for index, image in enumerate(images):
            if FileHandler.check_file(image):
                try:
                    ext = image.filename.rsplit('.', 1)[1].lower()
                    if len(images) == 1:
                        custom_filename = f"{safe_number}.{ext}"
                    else:
                        custom_filename = f"{safe_number}_{index + 1}.{ext}"
                    relative_path = FileHandler.save_file(
                        image, folder_key='UPLOAD_FOLDER_SPECIMEN_IMAGES',
                        filename=custom_filename,
                        relative_base=current_app.static_folder
                    )
                    # 记录绝对路径，用于 commit 失败时清理
                    abs_path = os.path.join(current_app.static_folder, relative_path.replace('/', os.sep))
                    saved_files.append(abs_path)
                except IOError as e:
                    db.session.rollback()
                    # 清理本次已保存的文件
                    for f in saved_files:
                        try:
                            os.remove(f)
                        except OSError:
                            pass
                    flash(f"图片保存失败: {e}", 'error')
                    return redirect(url_for('admin.upload_specimen'))
                img = SpecimenImage(
                    specimen_id=specimen.id,
                    image_path=relative_path,
                    sort_order=index + 1
                )
                db.session.add(img)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            # 清理已保存的孤立文件
            for f in saved_files:
                try:
                    os.remove(f)
                except OSError:
                    pass
            flash(f"标本编号 '{specimen_number}' 已存在（并发冲突）", 'error')
            return redirect(url_for('admin.upload_specimen'))

        flash("标本上传成功！", 'success')
        return redirect(url_for('admin.upload_specimen'))

    # ==================== GET 请求显示上传页面 ==================== #
    categories = SpecimenCategory.query.all()
    category_codes = {str(cat.id): cat.code for cat in categories if cat.code}
    return render_template('admin/upload_specimen.html', categories=categories, category_codes=category_codes)

# ==================== 批量上传标本 ==================== #

@admin_bp.route('/batch_upload')
@login_required
@admin_required
def batch_upload():
    """显示批量上传页面"""
    return render_template('admin/batch_upload.html')


@admin_bp.route('/batch_upload/template')
@login_required
@admin_required
def batch_upload_template():
    """动态生成模板 Excel 文件供下载"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = Workbook()
    # 删除默认 Sheet
    wb.remove(wb.active)

    categories = SpecimenCategory.query.order_by(SpecimenCategory.id).all()

    if not categories:
        flash('请先创建标本大类后再下载模板', 'error')
        return redirect(url_for('admin.batch_upload'))

    HEADERS = ['序号', '标本编号', '中文名', '拉丁名', '别名',
               '门', '纲', '目', '科', '属', '种',
               '采集人', '采集时间', '采集地点', '经度', '纬度',
               '鉴定人', '鉴定时间', '图片']

    # 表头样式
    header_font = Font(name='微软雅黑', bold=True, size=11, color='FFFFFF')
    header_fill = PatternFill(start_color='2C5F7C', end_color='2C5F7C', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    example_font = Font(name='微软雅黑', size=10)
    thin_border = Border(
        left=Side(style='thin', color='D0D0D0'),
        right=Side(style='thin', color='D0D0D0'),
        top=Side(style='thin', color='D0D0D0'),
        bottom=Side(style='thin', color='D0D0D0'),
    )

    for cat in categories:
        ws = wb.create_sheet(title=cat.name)

        # 写入表头（仅表头，不含示例数据行）
        for col_idx, header in enumerate(HEADERS, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border

        # 设置列宽
        col_widths = [6, 22, 18, 24, 14, 14, 14, 14, 14, 14, 14, 10, 14, 22, 14, 14, 10, 14, 22]
        for col_idx, width in enumerate(col_widths, 1):
            ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = width

        # Sheet 标签颜色（给每个大类一个不同颜色）
        tab_colors = ['FF2C5F7C', 'FF27AE60', 'FFB8934E', 'FF2D8A7B', 'FF8E44AD',
                      'FFE67E22', 'FF3498DB', 'FF1ABC9C', 'FFE74C3C', 'FFF39C12']
        color_idx = categories.index(cat) % len(tab_colors)
        ws.sheet_properties.tabColor = tab_colors[color_idx]

    # 输出到 BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    wb.close()

    from flask import send_file
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='标本批量导入模板.xlsx'
    )


@admin_bp.route('/batch_upload/validate', methods=['POST'])
@login_required
@admin_required
def batch_upload_validate():
    """
    上传 ZIP 并进行校验（AJAX 接口）。
    接收 ZIP 文件 → 解压 → 找 Excel → 三层校验 → 返回 JSON 结果。
    """
    # ---- 检查文件 ----
    zip_file = request.files.get('zip_file')
    if not zip_file or not zip_file.filename:
        return jsonify({'success': False, 'error': '请选择 ZIP 文件'})

    if not zip_file.filename.lower().endswith('.zip'):
        return jsonify({'success': False, 'error': '仅支持 .zip 格式文件'})

    # 检查文件大小
    max_zip_size = current_app.config.get('MAX_ZIP_SIZE', 100 * 1024 * 1024)
    zip_file.seek(0, os.SEEK_END)
    file_size = zip_file.tell()
    zip_file.seek(0)
    if file_size > max_zip_size:
        max_mb = max_zip_size // (1024 * 1024)
        return jsonify({'success': False, 'error': f'文件过大，最大支持 {max_mb}MB'})

    # ---- 创建唯一临时目录 ----
    temp_dir = current_app.config.get('TEMP_UPLOAD_DIR')
    if not temp_dir:
        temp_dir = os.path.join(os.path.dirname(__file__), '..', 'temp_uploads')
    session_id = uuid.uuid4().hex
    extract_dir = os.path.join(temp_dir, session_id)
    os.makedirs(extract_dir, exist_ok=True)

    try:
        # ---- 解压 ZIP ----
        with zipfile.ZipFile(zip_file) as zf:
            # 安全检查：防止 ZIP 炸弹
            total_uncompressed = sum(info.file_size for info in zf.infolist())
            if total_uncompressed > 500 * 1024 * 1024:  # 500MB 上限
                shutil.rmtree(extract_dir, ignore_errors=True)
                return jsonify({'success': False, 'error': 'ZIP 解压后内容过大（超过 500MB）'})

            zf.extractall(extract_dir)

        # ---- 查找 Excel 文件 ----
        xlsx_files = []
        for root, dirs, files in os.walk(extract_dir):
            for f in files:
                if f.lower().endswith('.xlsx') and not f.startswith('~$'):
                    xlsx_files.append(os.path.join(root, f))

        if not xlsx_files:
            shutil.rmtree(extract_dir, ignore_errors=True)
            return jsonify({'success': False, 'error': 'ZIP 中未找到 .xlsx 文件'})

        # 取第一个找到的 xlsx（如有多个，优先取根目录下的）
        xlsx_files.sort(key=lambda p: p.count(os.sep))
        xlsx_path = xlsx_files[0]

        # ---- 准备分类映射和已有编号 ----
        all_categories = SpecimenCategory.query.all()
        categories_by_name = {cat.name: cat for cat in all_categories}

        existing_numbers = {s[0] for s in Specimen.query.with_entities(Specimen.specimen_number).all()}

        # ---- 执行三层校验 ----
        max_image_size = current_app.config.get('MAX_IMAGE_SIZE', 1 * 1024 * 1024)
        result = parse_workbook(
            file_path=xlsx_path,
            categories_by_name=categories_by_name,
            existing_numbers=existing_numbers,
            image_dir=extract_dir,  # ZIP 解压目录即图片所在目录
            max_image_size=max_image_size
        )

        # ---- 将校验结果存入临时 JSON 文件（避免 session cookie 溢出） ----
        valid_rows = [r for r in result['rows'] if r['is_valid']]
        cache_file = os.path.join(extract_dir, '_batch_cache.json')
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump({'valid_rows': valid_rows, 'session_id': session_id}, f, ensure_ascii=False)

        # 只在 session 中存储 session_id（用于后续导入时定位文件）
        session['batch_session_id'] = session_id

        # ---- 构建 JSON 响应 ----
        response_data = {
            'success': True,
            'session_id': session_id,
            'sheet_errors': result['sheet_errors'],
            'all_category_names': result.get('all_category_names', []),
            'sheet_details': result.get('sheet_details', {}),
            'rows': [],
            'summary': result['summary'],
        }

        for row in result['rows']:
            response_data['rows'].append({
                'sheet_name': row['sheet_name'],
                'row_index': row['row_index'],
                'specimen_number': row['data'].get('specimen_number') or '',
                'chinese_name': row['data'].get('chinese_name') or '',
                'latin_name': row['data'].get('latin_name') or '',
                'is_valid': row['is_valid'],
                'errors': row['errors'],
            })

        return jsonify(response_data)

    except zipfile.BadZipFile:
        shutil.rmtree(extract_dir, ignore_errors=True)
        return jsonify({'success': False, 'error': '无效的 ZIP 文件，无法解压'})
    except Exception as e:
        shutil.rmtree(extract_dir, ignore_errors=True)
        current_app.logger.error(f'批量上传校验异常: {e}', exc_info=True)
        return jsonify({'success': False, 'error': f'校验过程出错: {str(e)}'})


@admin_bp.route('/batch_upload/import', methods=['POST'])
@login_required
@admin_required
def batch_upload_import():
    """
    确认导入校验通过的数据（AJAX 接口）。
    从 session 读取校验通过的行 → 逐行独立事务入库 → 返回结果。
    """
    session_id = session.get('batch_session_id')
    if not session_id:
        return jsonify({'success': False, 'error': '请先上传 ZIP 文件并完成校验'})

    # 从临时 JSON 文件中读取校验通过的数据
    temp_dir = current_app.config.get('TEMP_UPLOAD_DIR')
    if not temp_dir:
        temp_dir = os.path.join(os.path.dirname(__file__), '..', 'temp_uploads')
    extract_dir = os.path.join(temp_dir, session_id)

    if not os.path.isdir(extract_dir):
        return jsonify({'success': False, 'error': '临时文件已过期，请重新上传 ZIP 文件'})

    cache_file = os.path.join(extract_dir, '_batch_cache.json')
    if not os.path.exists(cache_file):
        return jsonify({'success': False, 'error': '校验数据已过期，请重新上传 ZIP 文件'})

    with open(cache_file, 'r', encoding='utf-8') as f:
        cache_data = json.load(f)

    valid_rows = cache_data.get('valid_rows', [])
    if not valid_rows:
        return jsonify({'success': False, 'error': '没有可导入的数据，请重新上传 ZIP 文件并校验'})

    upload_folder = current_app.config.get('UPLOAD_FOLDER_SPECIMEN_IMAGES')

    success_count = 0
    failed_rows = []

    for row in valid_rows:
        data = row['data']
        specimen_number = (data.get('specimen_number') or '').strip()
        category_id = row['category_id']

        try:
            # ---- 构建 Specimen 对象 ----
            specimen = Specimen(
                category_id=category_id,
                specimen_number=specimen_number,
                latin_name=data.get('latin_name'),
                chinese_name=data.get('chinese_name'),
                alias=data.get('alias'),
                phylum=data.get('phylum'),
                class_name=data.get('class_name'),
                order_name=data.get('order_name'),
                family=data.get('family'),
                genus=data.get('genus'),
                species=data.get('species'),
                collector=data.get('collector'),
                collect_location=data.get('collect_location'),
                appraiser=data.get('appraiser'),
                created_by=current_user.username,
                updated_by=current_user.username,
            )

            # ---- 采集时间 ----
            collect_time_str = data.get('collect_time')
            if collect_time_str:
                from app.utils.excel_util import _parse_date
                dt = _parse_date(collect_time_str)
                if dt:
                    specimen.collect_time = CHINA_TZ.localize(dt)
                else:
                    specimen.collect_time = now()
            else:
                specimen.collect_time = now()

            # ---- 鉴定时间 ----
            appraisal_time_str = data.get('appraisal_time')
            if appraisal_time_str:
                from app.utils.excel_util import _parse_date
                dt = _parse_date(appraisal_time_str)
                if dt:
                    specimen.appraisal_time = CHINA_TZ.localize(dt)

            # ---- 经纬度 ----
            lon_str = data.get('longitude')
            if lon_str:
                try:
                    specimen.longitude = float(lon_str)
                except (ValueError, TypeError):
                    pass

            lat_str = data.get('latitude')
            if lat_str:
                try:
                    specimen.latitude = float(lat_str)
                except (ValueError, TypeError):
                    pass

            db.session.add(specimen)
            copied_files = []  # 跟踪已复制的文件，commit 失败时清理
            db.session.flush()  # 获取 specimen.id

            # ---- 处理图片 ----
            image_filenames = data.get('image_filenames')
            if image_filenames:
                from app.utils.excel_util import _split_image_filenames
                filenames = _split_image_filenames(image_filenames)
                safe_number = re.sub(r'[\\/:*?"<>|]', '_', specimen_number)

                for img_index, fname in enumerate(filenames):
                    fname = fname.strip()
                    if not fname:
                        continue

                    src_path = _find_image_in_dir(fname, extract_dir)
                    if not src_path:
                        continue  # 图片不存在，跳过（校验阶段已报错）

                    ext = fname.rsplit('.', 1)[-1].lower()
                    if ext not in current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif'}):
                        continue

                    # 命名规则与单条上传一致
                    total_images = len([f for f in filenames if f.strip()])
                    if total_images == 1:
                        dest_filename = f"{safe_number}.{ext}"
                    else:
                        dest_filename = f"{safe_number}_{img_index + 1}.{ext}"

                    dest_path = os.path.join(upload_folder, dest_filename)

                    # 如果目标文件已存在，追加序号
                    if os.path.exists(dest_path):
                        base = dest_filename.rsplit('.', 1)[0]
                        counter = 1
                        while os.path.exists(os.path.join(upload_folder, f"{base}_{counter}.{ext}")):
                            counter += 1
                        dest_filename = f"{base}_{counter}.{ext}"
                        dest_path = os.path.join(upload_folder, dest_filename)

                    # 复制文件
                    shutil.copy2(src_path, dest_path)
                    copied_files.append(dest_path)

                    # 计算相对路径
                    rel_path = os.path.relpath(dest_path, current_app.static_folder).replace('\\', '/')

                    img = SpecimenImage(
                        specimen_id=specimen.id,
                        image_path=rel_path,
                        sort_order=img_index + 1
                    )
                    db.session.add(img)

            # ---- 提交该行 ----
            db.session.commit()
            success_count += 1

        except IntegrityError:
            db.session.rollback()
            # 清理已复制的孤立文件
            for f in copied_files:
                try:
                    os.remove(f)
                except OSError:
                    pass
            failed_rows.append({
                'sheet_name': row['sheet_name'],
                'row_index': row['row_index'],
                'specimen_number': specimen_number,
                'reason': f'标本编号 "{specimen_number}" 已存在（并发冲突）'
            })
        except Exception as e:
            db.session.rollback()
            # 清理已复制的孤立文件
            for f in copied_files:
                try:
                    os.remove(f)
                except OSError:
                    pass
            current_app.logger.error(f'批量导入行失败: {e}', exc_info=True)
            failed_rows.append({
                'sheet_name': row['sheet_name'],
                'row_index': row['row_index'],
                'specimen_number': specimen_number,
                'reason': str(e)
            })

    # ---- 清理临时目录 ----
    try:
        shutil.rmtree(extract_dir, ignore_errors=True)
    except Exception:
        pass

    # ---- 清除 session ----
    session.pop('batch_session_id', None)

    return jsonify({
        'success': True,
        'imported': success_count,
        'failed': len(failed_rows),
        'failed_rows': failed_rows,
    })


def _find_image_in_dir(filename: str, search_dir: str) -> str | None:
    """
    在指定目录及其子目录中递归查找图片文件。
    优先匹配根目录下的文件，然后深入子目录。
    """
    # 先在根目录查找
    direct_path = os.path.join(search_dir, filename)
    if os.path.isfile(direct_path):
        return direct_path

    # 递归查找
    for root, dirs, files in os.walk(search_dir):
        for f in files:
            if f == filename:
                return os.path.join(root, f)

    return None

# ==================== 编辑标本 ==================== #
@admin_bp.route('/specimens/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_specimen(id):
    specimen = Specimen.query.get_or_404(id)
    categories = SpecimenCategory.query.all()
    category_codes = {str(cat.id): cat.code for cat in categories if cat.code}

    if request.method == 'POST':
        old_specimen_number = specimen.specimen_number  # 修改前的编号快照
        category_id_int = _parse_int_form_value(request.form.get('category_id'))
        if category_id_int is None:
            flash("请选择有效的标本大类", 'error')
            return redirect(url_for('admin.edit_specimen', id=specimen.id))
        specimen.category_id = category_id_int
        specimen.specimen_number = request.form.get('specimen_number')
        specimen.chinese_name = request.form.get('chinese_name') or None
        specimen.latin_name = request.form.get('latin_name')
        specimen.alias = request.form.get('alias') or None
        specimen.phylum = request.form.get('phylum') or None
        specimen.class_name = request.form.get('class_name') or None
        specimen.order_name = request.form.get('order') or None
        specimen.family = request.form.get('family') or None
        specimen.genus = request.form.get('genus') or None
        specimen.species = request.form.get('species') or None
        specimen.collector = request.form.get('collector') or None

        # ---- 必填字段验证（门/纲/目/科/属） ----
        required_fields = [
            ('phylum', '门'),
            ('class_name', '纲'),
            ('order', '目'),
            ('family', '科'),
            ('genus', '属'),
        ]
        missing = []
        for field_name, label in required_fields:
            val = (request.form.get(field_name) or '').strip()
            if not val:
                missing.append(label)
        if missing:
            flash(f"以下必填字段不能为空：{'、'.join(missing)}", 'error')
            return redirect(url_for('admin.edit_specimen', id=specimen.id))

        # ---- 标本编号非空 + 唯一性检查（排除自身） ----
        new_number = request.form.get('specimen_number', '').strip()
        if not new_number:
            flash("标本编号不能为空", 'error')
            return redirect(url_for('admin.edit_specimen', id=specimen.id))

        existing = Specimen.query.filter(
            Specimen.specimen_number == new_number,
            Specimen.id != specimen.id
        ).first()
        if existing:
            flash(f"标本编号 '{new_number}' 已存在，请使用其他编号", 'error')
            return redirect(url_for('admin.edit_specimen', id=specimen.id))

        collect_time = _parse_datetime_form_value(request.form.get('collect_time'))
        if collect_time is not None:
            specimen.collect_time = collect_time

        specimen.collect_location = request.form.get('collect_location') or None

        specimen.longitude = _parse_float_form_value(request.form.get('longitude'))
        specimen.latitude = _parse_float_form_value(request.form.get('latitude'))

        specimen.appraiser = request.form.get('appraiser') or None
        specimen.appraisal_time = _parse_datetime_form_value(request.form.get('appraisal_time'))

        other_info = request.form.get('other_info')
        try:
            specimen.other_info = json.loads(other_info) if other_info else None
        except Exception:
            specimen.other_info = other_info or None

        # ---- 如果标本编号变更，计算重命名计划（暂不执行文件操作） ----
        pending_renames = []   # [(old_path, new_path)]
        if old_specimen_number != specimen.specimen_number:
            current_app.logger.info(
                f"标本编号变更: '{old_specimen_number}' -> '{specimen.specimen_number}', 计划重命名图片..."
            )
            upload_folder = current_app.config.get('UPLOAD_FOLDER_SPECIMEN_IMAGES')
            safe_new = re.sub(r'[\\/:*?"<>|]', '_', specimen.specimen_number)
            current_app.logger.info(f"图片上传目录: {upload_folder}, safe_new='{safe_new}'")

            # 构建待删除图片 ID 集合（这些不需要重命名，稍后会删掉）
            delete_ids_raw = request.form.get('delete_image_ids', '')
            delete_id_set = set()
            if delete_ids_raw:
                delete_id_set = {int(x) for x in delete_ids_raw.split(',') if x.strip()}

            # 剩余图片（不含本次要删除的）
            remaining_images = [img for img in specimen.images if img.id not in delete_id_set]
            total_remaining = len(remaining_images)
            current_app.logger.info(
                f"标本共 {len(specimen.images)} 张图片，"
                f"待删除 {len(delete_id_set)} 张，剩余 {total_remaining} 张"
            )

            for img in remaining_images:
                old_basename = os.path.basename(img.image_path)
                old_full_path = os.path.join(upload_folder, old_basename)
                ext = old_basename.rsplit('.', 1)[-1].lower()

                # 根据剩余图片数量决定命名格式
                if total_remaining == 1:
                    new_basename = f"{safe_new}.{ext}"
                else:
                    new_basename = f"{safe_new}_{img.sort_order}.{ext}"

                new_full_path = os.path.join(upload_folder, new_basename)
                current_app.logger.info(
                    f"  图片 id={img.id}: '{old_basename}' -> '{new_basename}' "
                    f"(total_remaining={total_remaining}, sort_order={img.sort_order})"
                )

                # 如果新旧文件名相同，跳过
                if old_basename == new_basename:
                    current_app.logger.info(f"  文件名未变化，跳过")
                    continue

                # 只记录重命名计划，暂不执行（等 DB commit 成功后再操作文件）
                if os.path.exists(old_full_path):
                    if os.path.exists(new_full_path):
                        current_app.logger.warning(f"目标文件已存在，跳过重命名: {new_full_path}")
                        continue
                    pending_renames.append((old_full_path, new_full_path))
                    current_app.logger.info(f"  已加入重命名队列: {old_full_path} -> {new_full_path}")
                else:
                    current_app.logger.warning(f"  源文件不存在，仅更新数据库路径: {old_full_path}")

                # 更新数据库中的路径（先改 DB，文件操作在 commit 之后）
                rel_dir = os.path.dirname(img.image_path)
                img.image_path = os.path.join(rel_dir, new_basename).replace('\\', '/')
                current_app.logger.info(f"  数据库路径已更新: '{img.image_path}'")

        # 处理图片删除 — 只删 DB 记录，文件操作延迟到 commit 之后
        pending_deletions = []  # [file_path]
        delete_image_ids_str = request.form.get('delete_image_ids', '')
        if delete_image_ids_str:
            delete_image_ids = [int(x) for x in delete_image_ids_str.split(',') if x.strip()]
            for img_id in delete_image_ids:
                img = SpecimenImage.query.get(img_id)
                if img and img.specimen_id == specimen.id:
                    upload_folder = current_app.config.get('UPLOAD_FOLDER_SPECIMEN_IMAGES')
                    file_full_path = os.path.join(upload_folder, os.path.basename(img.image_path))
                    if os.path.exists(file_full_path):
                        pending_deletions.append(file_full_path)
                    db.session.delete(img)

        # 处理新图片上传（以标本号命名）
        existing_count = SpecimenImage.query.filter_by(specimen_id=specimen.id).count()
        images = request.files.getlist('images')
        safe_number = re.sub(r'[\\/:*?"<>|]', '_', specimen.specimen_number)
        pending_new_files = []  # 用于 commit 失败时清理
        for index, image in enumerate(images):
            if FileHandler.check_file(image):
                try:
                    ext = image.filename.rsplit('.', 1)[1].lower()
                    seq = existing_count + index + 1
                    if len(images) == 1 and existing_count == 0:
                        custom_filename = f"{safe_number}.{ext}"
                    else:
                        custom_filename = f"{safe_number}_{seq}.{ext}"
                    relative_path = FileHandler.save_file(
                        image, folder_key='UPLOAD_FOLDER_SPECIMEN_IMAGES',
                        filename=custom_filename,
                        relative_base=current_app.static_folder
                    )
                except IOError as e:
                    db.session.rollback()
                    # 清理本次已保存的新文件
                    for f in pending_new_files:
                        try:
                            os.remove(f)
                        except OSError:
                            pass
                    flash(f"图片保存失败: {e}", 'error')
                    return redirect(url_for('admin.edit_specimen', id=specimen.id))
                # 记录绝对路径，用于 commit 失败时清理
                abs_path = os.path.join(current_app.static_folder, relative_path.replace('/', os.sep))
                pending_new_files.append(abs_path)
                img = SpecimenImage(
                    specimen_id=specimen.id,
                    image_path=relative_path,
                    sort_order=existing_count + index + 1
                )
                db.session.add(img)

        specimen.updated_by = current_user.username
        specimen.updated_at = now()

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            # 清理本次已保存的新文件
            for f in pending_new_files:
                try:
                    os.remove(f)
                except OSError:
                    pass
            flash(f"标本编号 '{specimen.specimen_number}' 已存在（并发冲突）", 'error')
            return redirect(url_for('admin.edit_specimen', id=specimen.id))

        # ====== DB 提交成功，执行文件操作 ====== #
        # 1. 执行延期重命名
        for old_path, new_path in pending_renames:
            try:
                os.rename(old_path, new_path)
                current_app.logger.info(f"重命名成功: {old_path} -> {new_path}")
            except OSError as e:
                current_app.logger.warning(f"重命名失败（数据库已更新）: {old_path} -> {new_path}, 错误: {e}")

        # 2. 执行延期删除
        for file_path in pending_deletions:
            try:
                os.remove(file_path)
                current_app.logger.info(f"删除文件成功: {file_path}")
            except OSError as e:
                current_app.logger.warning(f"删除文件失败: {file_path}, 错误: {e}")

        flash('标本编辑成功！', 'success')
        return redirect(url_for('admin.manage_specimens'))

    return render_template('admin/upload_specimen.html',
                           categories=categories,
                           specimen=specimen,
                           category_codes=category_codes)

# ==================== 删除标本 ==================== #
@admin_bp.route('/specimens/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_specimen(id):
    specimen = Specimen.query.get_or_404(id)

    upload_folder = current_app.config.get('UPLOAD_FOLDER_SPECIMEN_IMAGES')
    for img in specimen.images:
        file_full_path = os.path.join(upload_folder, os.path.basename(img.image_path))
        if os.path.exists(file_full_path):
            try:
                os.remove(file_full_path)
            except OSError as e:
                current_app.logger.warning(f"删除标本 {id} 的图片文件失败: {file_full_path}, 错误: {e}")

    db.session.delete(specimen)
    db.session.commit()

    flash('标本已删除！', 'success')
    return redirect(url_for('admin.manage_specimens'))