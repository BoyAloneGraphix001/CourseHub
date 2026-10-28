from flask import Blueprint, render_template, request, abort
from flask_login import current_user
from sqlalchemy import or_, func, and_
from sqlalchemy.orm import contains_eager, joinedload, selectinload
from app.extensions import db
from app.models import Course, Category, User, Section, Enrollment
from app.main.forms import SearchForm


main = Blueprint("main", __name__)


def public_courses():
    """Published courses whose instructor isn't suspended."""
    return (
        Course.query
        .join(User, Course.instructor_id == User.id)
        .filter(Course.is_published.is_(True), User.is_active_account.is_(True))
        .options(
            contains_eager(Course.instructor),
            joinedload(Course.category),
            selectinload(Course.sections).selectinload(Section.lessons),
        )
    )

# Home 
@main.route("/")
def index():
    courses = public_courses().order_by(Course.created_at.desc()).limit(3).all()
    categories = Category.query.order_by(Category.name).all()
    counts = dict(
        db.session.query(Category.id, func.count(Course.id))
        .outerjoin(Course, and_(Course.category_id == Category.id,
                                Course.is_published.is_(True)))
        .join(User, Course.instructor_id == User.id, isouter=True)
        .filter(or_(User.id.is_(None), User.is_active_account.is_(True)))
        .group_by(Category.id).all()
    )
    return render_template("main/index.html", courses=courses,
                           categories=categories, counts=counts)


# Courses 
@main.route("/courses")
def catalog():
    title = "All Courses | CourseHub"
    form = SearchForm(request.args)
    page = request.args.get("page", 1, type=int)

    q = form.q.data or "" if form.validate() else ""
    category = (form.category.data or "") if form.validate() else ""
    level = (form.level.data or "") if form.validate() else ""

    query = public_courses()
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Course.title.ilike(like), User.username.ilike(like)))
    if category:
        query = (query.join(Category, Course.category_id == Category.id)
                      .filter(Category.name == category))
    if level:
        query = query.filter(Course.level == level)

    pagination = (query.order_by(Course.created_at.desc())
                       .paginate(page=page, per_page=9, error_out=False))
    categories = Category.query.order_by(Category.name).all()
    return render_template("main/catalog.html", title=title, pagination=pagination,
                           categories=categories, q=q, category=category,
                           level=level, form=form)


@main.route("/courses/<int:course_id>")
def course_detail(course_id):
    course = (Course.query
              .options(joinedload(Course.instructor), joinedload(Course.category),
                       selectinload(Course.sections).selectinload(Section.lessons))
              .filter_by(id=course_id).first_or_404())

    is_owner = current_user.is_authenticated and course.instructor_id == current_user.id
    is_admin = current_user.is_authenticated and current_user.is_admin
    visible = course.is_published and course.instructor.is_active_account
    if not (visible or is_owner or is_admin):
        abort(404)

    enrollment, done_ids = None, set()
    if current_user.is_authenticated:
        enrollment = Enrollment.query.filter_by(
            student_id=current_user.id, course_id=course.id).first()
        if enrollment:
            done_ids = enrollment.completed_lesson_ids

    lessons = [l for s in course.sections for l in s.lessons]
    resume = next((l for l in lessons if l.id not in done_ids),
                  lessons[0] if lessons else None)

    return render_template("main/course_detail.html", course=course,
                           enrollment=enrollment, done_ids=done_ids,
                           resume=resume, is_owner=is_owner)

# Instructor 
@main.route("/instructors/<int:user_id>")
def instructor_profile(user_id):
    title = "Instructor || CourseHub"
    instructor = User.query.get_or_404(user_id)
    if not instructor.is_active_account or not (instructor.is_instructor or instructor.courses):
        abort(404)
    courses = (public_courses().filter(Course.instructor_id == instructor.id)
               .order_by(Course.created_at.desc()).all())
    return render_template("main/instructor_profile.html",
                           instructor=instructor, courses=courses, title=title)