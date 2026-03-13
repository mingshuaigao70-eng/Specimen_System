from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
import os

from ..extensions import db
from ..models import User, Specimen, SpecimenImage, SpecimenCategory
from ..utils.password import generate_scrypt_hash
from ..utils.file_util import allowed_file

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
    return render_template('admin/categories.html', categories=categories)


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

# ====================上传标本==================== #
@admin_bp.route('/upload_specimen', methods=['GET', 'POST'])
@login_required
@admin_required
def upload_specimen():
    if request.method == 'POST':
        # 获取表单
        category_id = request.form.get('category_id')
        specimen_number = request.form.get('specimen_number')
        chinese_name = request.form.get('chinese_name')
        latin_name = request.form.get('latin_name')
        collector = request.form.get('collector')
        collect_time_str = request.form.get('collect_time')

        # 转换时间
        collect_time = datetime.strptime(collect_time_str, "%Y-%m-%dT%H:%M") if collect_time_str else datetime.utcnow()

        # 保存标本信息
        specimen = Specimen(
            category_id=int(category_id),
            specimen_number=specimen_number,
            chinese_name=chinese_name,
            latin_name=latin_name,
            collector=collector,
            collect_time=collect_time,
            created_by=current_user.username,
            updated_by=current_user.username,
        )
        db.session.add(specimen)
        db.session.commit()  # 提交生成 ID

        # 处理多张图片
        images = request.files.getlist('images')
        upload_folder = current_app.config['UPLOAD_FOLDER_IMAGES']

        for index, image in enumerate(images):
            if image and allowed_file(image.filename):
                ext = image.filename.rsplit('.', 1)[1].lower()
                filename = f"{specimen.id}_{index+1}.{ext}"
                filepath = os.path.join(upload_folder, filename)
                relative_path = os.path.join('images', filename)

                # 保存文件
                image.save(filepath)

                # 保存数据库
                img = SpecimenImage(
                    specimen_id=specimen.id,
                    image_path=relative_path,
                    sort_order=index+1
                )
                db.session.add(img)

        db.session.commit()
        flash("标本上传成功！", 'success')
        return redirect(url_for('admin.manage_specimens'))

    # GET 请求显示上传页面
    categories = SpecimenCategory.query.all()
    return render_template('admin/upload_specimen.html', categories=categories)