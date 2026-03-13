from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import Specimen, SpecimenImage
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def index():
    specimens =Specimen.query.all()
    return render_template('index.html', user=current_user, specimens=specimens)