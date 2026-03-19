from flask import Blueprint, render_template
from flask_login import current_user, login_required
from ..models import SpecimenCategory

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required  # 如果首页不需要登录可以去掉
def index():
    # 查询数据库获取标本大类
    categories = SpecimenCategory.query.all()
    return render_template('main/index.html', categories=categories, current_user=current_user)