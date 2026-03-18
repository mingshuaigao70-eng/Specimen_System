from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
import os

from ..extensions import db
from ..models import User, Specimen, SpecimenImage, SpecimenCategory
from ..utils.password import generate_scrypt_hash
from app.utils.file_util import FileHandler
import json

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
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
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
    category.updated_at = datetime.utcnow()
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
@login_required  # 确保用户已登录
@admin_required  # 确保用户具有管理员权限
def upload_specimen():
    if request.method == 'POST':
        # ==================== 获取表单数据 ==================== #
        category_id = request.form.get('category_id')  # 标本大类 ID
        specimen_number = request.form.get('specimen_number')  # 标本编号
        chinese_name = request.form.get('chinese_name') or None  # 中文名，可为空
        latin_name = request.form.get('latin_name')  # 拉丁名，必填
        alias = request.form.get('alias') or None  # 别名，可为空
        phylum = request.form.get('phylum') or None  # 门，可为空
        class_name = request.form.get('class_name') or None  # 纲，可为空
        order_name = request.form.get('order') or None  # 目，可为空
        family = request.form.get('family') or None  # 科，可为空
        genus = request.form.get('genus') or None  # 属，可为空
        species = request.form.get('species') or None  # 种，可为空
        collector = request.form.get('collector') or None  # 采集人，可为空
        collect_time_str = request.form.get('collect_time')  # 采集时间字符串
        collect_time = datetime.strptime(collect_time_str, "%Y-%m-%dT%H:%M") if collect_time_str else datetime.utcnow()
        # 如果表单没有提供采集时间，则默认当前时间
        collect_location = request.form.get('collect_location') or None  # 采集地点，可为空

        # ==================== 经纬度处理 ==================== #
        longitude = request.form.get('longitude')
        latitude = request.form.get('latitude')
        # 将空字符串转换为 None，非空则转 float
        longitude = float(longitude) if longitude else None
        latitude = float(latitude) if latitude else None

        # ==================== 鉴定信息 ==================== #
        appraiser = request.form.get('appraiser') or None  # 鉴定人，可为空
        appraisal_time_str = request.form.get('appraisal_time')
        appraisal_time = datetime.strptime(appraisal_time_str, "%Y-%m-%dT%H:%M") if appraisal_time_str else None
        # 如果表单没有提供鉴定时间，则为 None

        # ==================== 其他信息（JSON 或文本） ==================== #
        other_info = request.form.get('other_info')
        # 尝试解析 JSON，如果失败则按文本存储
        try:
            other_info_json = json.loads(other_info) if other_info else None
        except Exception:
            other_info_json = other_info or None

        # ==================== 创建 Specimen 实例 ==================== #
        specimen = Specimen(
            category_id=int(category_id),  # 大类 ID
            specimen_number=specimen_number,  # 标本编号
            chinese_name=chinese_name,  # 中文名
            latin_name=latin_name,  # 拉丁名
            alias=alias,  # 别名
            phylum=phylum,  # 门
            class_name=class_name,  # 纲
            order_name=order_name,  # 目
            family=family,  # 科
            genus=genus,  # 属
            species=species,  # 种
            collector=collector,  # 采集人
            collect_time=collect_time,  # 采集时间
            collect_location=collect_location,  # 采集地点
            longitude=longitude,  # 经度
            latitude=latitude,  # 纬度
            appraiser=appraiser,  # 鉴定人
            appraisal_time=appraisal_time,  # 鉴定时间
            other_info=other_info_json,  # 其他信息
            created_by=current_user.username,  # 创建人
            updated_by=current_user.username,  # 更新人
            # ⚠️ 不要手动传 created_at/updated_at，SQLAlchemy 会自动填充
        )
        db.session.add(specimen)
        db.session.commit()  # 提交生成 ID，方便图片关联

        # ==================== 处理多张图片 ==================== #
        images = request.files.getlist('images')  # 获取上传的文件列表
        for index, image in enumerate(images):
            # 检查文件类型和大小
            if FileHandler.check_file(image):
                # 自动生成唯一文件名并保存到指定文件夹
                relative_path = FileHandler.save_file(image, folder_key='UPLOAD_FOLDER_IMAGES')
                # 保存图片信息到数据库
                img = SpecimenImage(
                    specimen_id=specimen.id,  # 关联标本 ID
                    image_path=relative_path,  # 文件相对路径
                    sort_order=index + 1  # 排序号
                )
                db.session.add(img)

        db.session.commit()  # 提交所有图片记录

        flash("标本上传成功！", 'success')
        return redirect(url_for('admin.upload_specimen'))

    # ==================== GET 请求显示上传页面 ==================== #
    categories = SpecimenCategory.query.all()  # 获取所有标本大类
    return render_template('admin/upload_specimen.html', categories=categories)