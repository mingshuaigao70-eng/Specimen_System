from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import User, FishSpecimen
from app.extensions import db

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/')
@login_required
def dashboard():
    if not current_user.is_admin:
        flash("无权限访问")
        return redirect(url_for('main.index'))
    users = User.query.all()
    specimens = FishSpecimen.query.all()
    return render_template('admin_dashboard.html', users=users, specimens=specimens)

@admin_bp.route('/upload_specimen', methods=['GET', 'POST'])
@login_required
def upload_specimen():
    if not current_user.is_admin:
        flash("无权限操作")
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        try:
            specimen = FishSpecimen(
                code=request.form.get('code'),
                chinese_name=request.form.get('chinese_name'),
                scientific_name=request.form.get('scientific_name'),
                kingdom=request.form.get('kingdom', ''),
                phylum=request.form.get('phylum', ''),
                class_=request.form.get('class_', ''),
                order=request.form.get('order', ''),
                family=request.form.get('family', ''),
                genus=request.form.get('genus', ''),
                species=request.form.get('species', ''),
                collector=request.form.get('collector', ''),
                location=request.form.get('location', ''),
                category=request.form.get('category', '鱼类')
            )
            db.session.add(specimen)
            db.session.commit()
            flash("标本上传成功")
            return redirect(url_for('admin.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f"上传失败: {str(e)}")
    return render_template('admin_upload_specimen.html')