from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
from ..extensions import db
from ..models import User, Specimen, SpecimenImage, SpecimenCategory
from ..utils.password import generate_scrypt_hash
from app.utils.file_util import FileHandler
import json
from app.utils.time_utils import now , CHINA_TZ

admin_bp = Blueprint('admin', __name__)

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

# -------------------- 平台首页 -------------------- #
@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    default_url = '/users' if current_user.role == 'superadmin' else '/specimens'
    return render_template('admin/admin_dashboard.html', default_url=default_url)

# ==================== 用户管理 ==================== #
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
        username = request.form['username']
        role = request.form['role']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash('用户名已存在！', 'error')
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
        user.username = request.form['username']
        user.role = request.form['role']
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
    description = request.form.get('description')
    if not name:
        flash('类别名称不能为空', 'warning')
        return redirect(url_for('admin.list_categories'))

    if SpecimenCategory.query.filter_by(name=name).first():
        flash('该类别已存在', 'warning')
        return redirect(url_for('admin.list_categories'))

    category = SpecimenCategory(
        name=name,
        description=description,
        created_by=current_user.username,
        updated_by=current_user.username,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
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
    description = request.form.get('description')
    if not new_name:
        flash('类别名称不能为空', 'warning')
        return redirect(url_for('admin.list_categories'))

    # 检查是否重复
    exists = SpecimenCategory.query.filter(
        SpecimenCategory.name == new_name,
        SpecimenCategory.id != id
    ).first()
    if exists:
        flash('该类别名称已存在', 'warning')
        return redirect(url_for('admin.list_categories'))

    category.name = new_name
    category.description = description
    category.updated_by = current_user.username
    category.updated_at = datetime.now()
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
    db.session.delete(category)
    db.session.commit()
    flash('大类删除成功', 'success')
    return redirect(url_for('admin.list_categories'))

# ==================== 标本信息维护 ==================== #
@admin_bp.route('/specimens')
@login_required
@admin_required
def manage_specimens():
    specimens = Specimen.query.all()
    return render_template('admin/admin_specimen_management.html', specimens=specimens)

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

        # 采集时间
        collect_time_str = request.form.get('collect_time')
        if collect_time_str:
            collect_time = datetime.strptime(collect_time_str, "%Y-%m-%dT%H:%M")
            collect_time = CHINA_TZ.localize(collect_time)
        else:
            collect_time = now()

        collect_location = request.form.get('collect_location') or None

        # ==================== 经纬度处理 ==================== #
        longitude = request.form.get('longitude')
        latitude = request.form.get('latitude')
        longitude = float(longitude) if longitude else None
        latitude = float(latitude) if latitude else None

        # ==================== 鉴定信息 ==================== #
        appraiser = request.form.get('appraiser') or None
        appraisal_time_str = request.form.get('appraisal_time')
        if appraisal_time_str:
            appraisal_time = datetime.strptime(appraisal_time_str, "%Y-%m-%dT%H:%M")
            appraisal_time = CHINA_TZ.localize(appraisal_time)
        else:
            appraisal_time = None

        # ==================== 其他信息（JSON 或文本） ==================== #
        other_info = request.form.get('other_info')
        try:
            other_info_json = json.loads(other_info) if other_info else None
        except Exception:
            other_info_json = other_info or None

        # ==================== 创建 Specimen 实例 ==================== #
        specimen = Specimen(
            category_id=int(category_id),
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
        db.session.commit()

        # ==================== 处理多张图片 ==================== #
        images = request.files.getlist('images')
        for index, image in enumerate(images):
            if FileHandler.check_file(image):
                relative_path = FileHandler.save_file(image, folder_key='UPLOAD_FOLDER_IMAGES')
                img = SpecimenImage(
                    specimen_id=specimen.id,
                    image_path=relative_path,
                    sort_order=index + 1
                )
                db.session.add(img)

        db.session.commit()

        flash("标本上传成功！", 'success')
        return redirect(url_for('admin.upload_specimen'))

    # ==================== GET 请求显示上传页面 ==================== #
    categories = SpecimenCategory.query.all()
    return render_template('admin/upload_specimen.html', categories=categories)