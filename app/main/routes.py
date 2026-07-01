from flask import Blueprint, render_template, request, redirect, url_for, current_app, flash
from flask_login import current_user, login_required
from ..models import SpecimenCategory, Specimen, SpecimenImage, PageContent
from ..extensions import db
from ..utils.search_utils import build_specimen_search_filter
from app.utils.time_utils import CHINA_TZ
from sqlalchemy.orm import selectinload
import os

main_bp = Blueprint('main', __name__)

# ==================== 主页面（需登录） ==================== #
@main_bp.route('/')
@login_required
def index():
    categories = SpecimenCategory.query.options(
        selectinload(SpecimenCategory.specimens)
    ).all()

    # 为每个分类查找对应图片（优先使用上传的封面图，其次按名称匹配）
    category_images = {}
    for cat in categories:
        if cat.image:
            # 使用数据库存储的图片路径
            img_full = os.path.join(current_app.config['UPLOAD_FOLDER_CATEGORY_IMAGES'], os.path.basename(cat.image))
            if os.path.exists(img_full):
                category_images[cat.id] = url_for('static', filename=f'images/public/{os.path.basename(cat.image)}')
                continue
        # 回退：按类别名称查找
        for ext in ('.jpg', '.png', '.jpeg'):
            img_rel = f'images/public/{cat.name}{ext}'
            if os.path.exists(os.path.join(current_app.static_folder, img_rel)):
                category_images[cat.id] = url_for('static', filename=img_rel)
                break

    # 首页横幅背景图（可配置，回退到默认图）
    banner_row = PageContent.query.filter_by(page='landing', section='banner_image').first()
    banner_image_url = None
    if banner_row and banner_row.content:
        banner_path = os.path.join(current_app.config['UPLOAD_FOLDER_CATEGORY_IMAGES'], os.path.basename(banner_row.content))
        if os.path.exists(banner_path):
            banner_image_url = url_for('static', filename=f'images/public/{os.path.basename(banner_row.content)}')
    if not banner_image_url:
        default_banner = os.path.join(current_app.static_folder, 'images/public/huanglanjiaojie.png')
        if os.path.exists(default_banner):
            banner_image_url = url_for('static', filename='images/public/huanglanjiaojie.png')

    return render_template('main/index.html',
                           categories=categories,
                           category_images=category_images,
                           banner_image_url=banner_image_url,
                           current_user=current_user)

# ==================== 关于我们（需登录） ==================== #
@main_bp.route('/about')
@login_required
def about():
    rows = PageContent.query.filter_by(page='about').all()
    content = {row.section: row.content for row in rows}
    return render_template('main/about.html', content=content)

# ==================== 标本详情 ==================== #
@main_bp.route('/specimen/<int:id>')
@login_required
def specimen_detail(id):
    specimen = Specimen.query.get_or_404(id)
    images = SpecimenImage.query.filter_by(specimen_id=id).order_by(SpecimenImage.sort_order).all()
    return render_template('main/specimen_detail.html',
                           specimen=specimen,
                           images=images)

# ==================== 标本列表（按分类筛选） ==================== #
@main_bp.route('/category/<int:category_id>')
@login_required
def specimen_list(category_id):
    category = SpecimenCategory.query.get_or_404(category_id)

    page = request.args.get('page', 1, type=int)
    per_page = 10

    # ---- 文本输入筛选（右侧） ----
    chinese_name_f = request.args.get('chinese_name', '').strip()
    latin_name_f = request.args.get('latin_name', '').strip()

    # ---- 级联下拉筛选（左侧） ----
    phylum_f = request.args.get('phylum', '').strip()
    class_f = request.args.get('class_name', '').strip()
    order_f = request.args.get('order_name', '').strip()
    family_f = request.args.get('family', '').strip()
    genus_f = request.args.get('genus', '').strip()
    species_f = request.args.get('species', '').strip()

    query = Specimen.query.options(
        selectinload(Specimen.images)
    ).filter_by(category_id=category_id)

    # 大类总数（不受筛选影响）
    category_total = Specimen.query.filter_by(category_id=category_id).count()

    # 文本输入 ILIKE 筛选
    if chinese_name_f:
        query = query.filter(Specimen.chinese_name.ilike(f'%{chinese_name_f}%'))
    if latin_name_f:
        query = query.filter(Specimen.latin_name.ilike(f'%{latin_name_f}%'))

    # 级联下拉筛选 — 用 ILIKE 兼容精确值和模糊输入
    if phylum_f:
        query = query.filter(Specimen.phylum.ilike(f'%{phylum_f}%'))
    if class_f:
        query = query.filter(Specimen.class_name.ilike(f'%{class_f}%'))
    if order_f:
        query = query.filter(Specimen.order_name.ilike(f'%{order_f}%'))
    if family_f:
        query = query.filter(Specimen.family.ilike(f'%{family_f}%'))
    if genus_f:
        query = query.filter(Specimen.genus.ilike(f'%{genus_f}%'))
    if species_f:
        query = query.filter(Specimen.species.ilike(f'%{species_f}%'))

    pagination = query.order_by(Specimen.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    specimens = pagination.items

    # ---- 级联下拉选项 ----
    def level_options(field, parent_filters):
        q = db.session.query(field, db.func.count(Specimen.id)).filter(
            Specimen.category_id == category_id,
            field != None,
            field != ''
        )
        for parent_field, parent_value in parent_filters:
            if parent_value:
                q = q.filter(parent_field.ilike(f'%{parent_value}%'))
        return [(r[0], r[1]) for r in q.group_by(field).order_by(field).all()]

    filter_map = {
        'phylum': (Specimen.phylum, phylum_f),
        'class_name': (Specimen.class_name, class_f),
        'order_name': (Specimen.order_name, order_f),
        'family': (Specimen.family, family_f),
        'genus': (Specimen.genus, genus_f),
        'species': (Specimen.species, species_f),
    }

    filter_labels = [('phylum','门'),('class_name','纲'),('order_name','目'),('family','科'),('genus','属'),('species','种')]

    filter_levels = []
    parent_filters = []
    for filter_key, label in filter_labels:
        field, current_val = filter_map[filter_key]
        options = level_options(field, parent_filters)
        if options:
            filter_levels.append({
                'filter_key': filter_key,
                'label': label,
                'options': options,
                'current_value': current_val,
            })
        if current_val:
            parent_filters.append((field, current_val))
        else:
            break

    current_filters = {
        'chinese_name': chinese_name_f, 'latin_name': latin_name_f,
        'phylum': phylum_f, 'class_name': class_f, 'order_name': order_f,
        'family': family_f, 'genus': genus_f, 'species': species_f,
    }

    return render_template('main/specimen_list.html',
                           specimens=specimens,
                           category=category,
                           pagination=pagination,
                           category_total=category_total,
                           filter_levels=filter_levels,
                           current_filters=current_filters)

# ==================== 搜索 ==================== #
@main_bp.route('/search')
@login_required
def search():
    q = request.args.get('q', '').strip()
    search_filter = build_specimen_search_filter(q)

    if search_filter is None:
        if not q:
            flash('请输入关键词', 'warning')
        else:
            flash('关键词至少需要2个字符', 'warning')
        return redirect(url_for('main.index'))

    page = request.args.get('page', 1, type=int)
    per_page = 24
    pagination = Specimen.query.options(selectinload(Specimen.images)).filter(search_filter) \
        .order_by(Specimen.id.desc()) \
        .paginate(page=page, per_page=per_page, error_out=False)

    return render_template('search_results.html',
                           query=q,
                           results=pagination.items,
                           pagination=pagination,
                           result_count=pagination.total)
