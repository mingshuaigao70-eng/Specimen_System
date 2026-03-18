from .extensions import db
from flask_login import UserMixin
from datetime import datetime

class User(db.Model, UserMixin):
    __tablename__ = 'user'  # 确保表名和数据库一致

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='用户ID')
    username = db.Column(db.String(50), unique=True, nullable=False, comment='用户名')
    password_hash = db.Column(db.String(200), nullable=False, comment='密码哈希值')
    # 角色字段
    role = db.Column(db.String(20), nullable=False, default='user',
                     comment='角色：superadmin/超级管理员，admin/管理员，user/普通用户')

    # 虚拟字段 is_admin
    @property
    def is_admin(self):
        return self.role in ('superadmin', 'admin')

class Specimen(db.Model):
    __tablename__ = 'specimen'

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('specimen_category.id'), nullable=False)
    specimen_number = db.Column(db.String(50), unique=True, nullable=False)
    chinese_name = db.Column(db.String(100))
    latin_name = db.Column(db.String(200), nullable=False)
    alias = db.Column(db.Text)
    phylum = db.Column(db.String(50))
    class_name = db.Column(db.String(50))
    order_name = db.Column("order", db.String(50))
    family = db.Column(db.String(50))
    genus = db.Column(db.String(50))
    species = db.Column(db.String(50))
    collector = db.Column(db.String(50))
    collect_time = db.Column(db.DateTime, nullable=False)
    collect_location = db.Column(db.String(255))

    longitude = db.Column(db.Numeric(10,7))
    latitude = db.Column(db.Numeric(10,7))

    appraiser = db.Column(db.String(50))
    appraisal_time = db.Column(db.DateTime)

    created_by = db.Column(db.String(50))
    updated_by = db.Column(db.String(50))

    other_info = db.Column(db.JSON)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    images = db.relationship('SpecimenImage', cascade='all, delete-orphan', back_populates='specimen')

    category = db.relationship('SpecimenCategory', backref='specimens')

class SpecimenImage(db.Model):
    __tablename__ = 'specimen_image'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='图片ID')
    specimen_id = db.Column(
        db.Integer,
        db.ForeignKey('specimen.id', ondelete='CASCADE'),  # 这里添加 ondelete='CASCADE'
        nullable=False,
        comment='外键，关联标本表 specimen.id'
    )
    sort_order = db.Column(db.Integer, default=0, comment='图片顺序')  # ← 新加字段
    image_path = db.Column(db.String(255), nullable=False, comment='图片路径')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, comment='上传时间')

    specimen = db.relationship('Specimen', back_populates='images')
class SpecimenCategory(db.Model):
    __tablename__ = 'specimen_category'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='大类ID')
    name = db.Column(db.String(100), unique=True, nullable=False, comment='类别名称')
    description = db.Column(db.Text, comment='说明（可选）')
    created_by = db.Column(db.String(50), comment='创建人')
    updated_by = db.Column(db.String(50), comment='修改人')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment='最后更新时间'
    )
    def __repr__(self):
        return f"<SpecimenCategory {self.name}>"