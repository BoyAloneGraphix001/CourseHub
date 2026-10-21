from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user
from sqlalchemy import func, or_
from sqlalchemy.orm import contains_eager, joinedload, selectinload

from app.extensions import db, login_manager
from app.models import User, Course, Category, Enrollment, Report
from app.admin.forms import CategoryForm
from app.utils import is_safe_redirect

admin = Blueprint("admin", __name__)


@admin.before_request
def guard():
    if not current_user.is_authenticated:
        return login_manager.unauthorized()          # redirects to login, keeps ?next=
    if not current_user.is_admin:
        abort(403)


@admin.context_processor
def sidebar_counts():
    """Numbers shown in the sidebar on every admin page."""
    return {"admin_counts": {
        "users": User.query.count(),
        "courses": Course.query.count(),
        "reports": Report.query.filter_by(status="open").count(),
    }}


def back(default):
    """Return to the page the action came from (only same-site URLs)."""
    target = request.form.get("next")
    return redirect(target if is_safe_redirect(target) else default)


# Overview / Dashboard 
@admin.route("/")
def dashboard():
    title = "Admin overview || CourseHub"
    stats = {
        "users": User.query.count(),
        "instructors": User.query.filter_by(is_instructor=True).count(),
        "courses": Course.query.count(),
        "published": Course.query.filter_by(is_published=True).count(),
        "enrollments": Enrollment.query.count(),
        "reports": Report.query.filter_by(status="open").count(),
    }
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    open_reports = (Report.query
                    .options(joinedload(Report.course), joinedload(Report.reporter))
                    .filter_by(status="open")
                    .order_by(Report.created_at.desc()).limit(5).all())
    return render_template("admin/dashboard.html", stats=stats,
                           recent_users=recent_users, open_reports=open_reports, title=title)


# Users 
@admin.route("/users")
def users():
    title = "Admin Users || CourseHub"
    q = request.args.get("q", "").strip()
    role = request.args.get("role", "")
    page = request.args.get("page", 1, type=int)

    query = User.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.username.ilike(like), User.email.ilike(like)))
    if role == "instructor":
        query = query.filter(User.is_instructor.is_(True))
    elif role == "admin":
        query = query.filter(User.is_admin.is_(True))
    elif role == "suspended":
        query = query.filter(User.is_active_account.is_(False))

    pagination = (query.order_by(User.created_at.desc())
                       .paginate(page=page, per_page=15, error_out=False))
    return render_template("admin/users.html", pagination=pagination, q=q, role=role, title=title)

# Users toggle 
@admin.route("/users/<int:user_id>/toggle", methods=["POST"])
def toggle_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("You can't suspend your own account.", "warning")
    elif user.is_admin:
        flash("Admin accounts can't be suspended here.", "warning")
    else:
        user.is_active_account = not user.is_active_account
        db.session.commit()
        flash(f"{user.username} has been "
              f"{'restored' if user.is_active_account else 'suspended'}.", "success")
    return back(url_for("admin.users"))


# Courses 
@admin.route("/courses")
def courses():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    page = request.args.get("page", 1, type=int)

    query = (Course.query
             .join(User, Course.instructor_id == User.id)
             .options(contains_eager(Course.instructor),
                      joinedload(Course.category),
                      selectinload(Course.enrollments)))
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Course.title.ilike(like), User.username.ilike(like)))
    if status == "published":
        query = query.filter(Course.is_published.is_(True))
    elif status == "draft":
        query = query.filter(Course.is_published.is_(False))

    pagination = (query.order_by(Course.created_at.desc())
                       .paginate(page=page, per_page=15, error_out=False))
    return render_template("admin/courses.html", pagination=pagination, q=q, status=status)

# Courses toggle 
@admin.route("/courses/<int:course_id>/toggle", methods=["POST"])
def toggle_course(course_id):
    course = db.get_or_404(Course, course_id)
    course.is_published = not course.is_published
    db.session.commit()
    flash(f"'{course.title}' is now "
          f"{'published' if course.is_published else 'unpublished'}.", "success")
    return back(url_for("admin.courses"))


# Reports 
@admin.route("/reports")
def reports():
    title = "Admin Reports || CourseHub"
    status = request.args.get("status", "open")
    page = request.args.get("page", 1, type=int)

    query = Report.query.options(
        joinedload(Report.course).joinedload(Course.instructor),
        joinedload(Report.reporter))
    if status in ("open", "resolved"):
        query = query.filter(Report.status == status)
    else:
        status = "all"

    pagination = (query.order_by(Report.created_at.desc())
                       .paginate(page=page, per_page=10, error_out=False))
    return render_template("admin/reports.html", pagination=pagination, status=status, title=title)

# Resolve Reports 
@admin.route("/reports/<int:report_id>/resolve", methods=["POST"])
def resolve_report(report_id):
    report = db.get_or_404(Report, report_id)
    report.status = "resolved"
    db.session.commit()
    flash("Report marked as resolved.", "success")
    return back(url_for("admin.reports"))

# Unpublish Reports 
@admin.route("/reports/<int:report_id>/unpublish", methods=["POST"])
def unpublish_reported(report_id):
    """Take the reported course offline and close every open report on it."""
    report = db.get_or_404(Report, report_id)
    course = report.course
    course.is_published = False
    Report.query.filter_by(course_id=course.id, status="open").update({"status": "resolved"})
    db.session.commit()
    flash(f"'{course.title}' was unpublished and its reports resolved.", "success")
    return back(url_for("admin.reports"))


# Categories 
@admin.route("/categories", methods=["GET", "POST"])
def categories():
    title = "Admin categories || CourseHub"
    form = CategoryForm()
    if form.validate_on_submit():
        db.session.add(Category(name=form.name.data.strip()))
        db.session.commit()
        flash("Category added.", "success")
        return redirect(url_for("admin.categories"))

    rows = (db.session.query(Category, func.count(Course.id))
            .outerjoin(Course, Course.category_id == Category.id)
            .group_by(Category.id)
            .order_by(Category.name).all())
    return render_template("admin/categories.html", form=form, rows=rows, title=title)

# Rename Category 
@admin.route("/categories/<int:category_id>/rename", methods=["POST"])
def rename_category(category_id):
    category = db.get_or_404(Category, category_id)
    form = CategoryForm(exclude_id=category.id)
    if form.validate_on_submit():
        category.name = form.name.data.strip()
        db.session.commit()
        flash("Category renamed.", "success")
    else:
        flash(form.name.errors[0] if form.name.errors else "Couldn't rename that category.", "danger")
    return redirect(url_for("admin.categories"))

# Delete Category
@admin.route("/categories/<int:category_id>/delete", methods=["POST"])
def delete_category(category_id):
    category = db.get_or_404(Category, category_id)
    if category.courses:
        flash("This category still has courses. Move or remove them first.", "warning")
    else:
        db.session.delete(category)
        db.session.commit()
        flash("Category deleted.", "success")
    return redirect(url_for("admin.categories"))