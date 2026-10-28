from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db, login_manager
from app.models import Course, Category, Section, Lesson, Enrollment
from app.instructor.forms import CourseForm, SectionForm, LessonForm
from app.utils import save_picture, delete_picture, to_embed_url, is_safe_redirect
from werkzeug.datastructures import FileStorage

instructor = Blueprint("instructor", __name__)


# ───────────── Access: logged-in instructors only ─────────────
@instructor.before_request
def guard():
    if not current_user.is_authenticated:
        return login_manager.unauthorized()
    if not current_user.is_instructor:
        return render_template("instructor/become.html")


@instructor.context_processor
def sidebar_data():
    if not current_user.is_authenticated or not current_user.is_instructor:
        return {}
    mine = Course.query.filter_by(instructor_id=current_user.id)
    learners = (db.session.query(func.count(Enrollment.id))
                .join(Course, Enrollment.course_id == Course.id)
                .filter(Course.instructor_id == current_user.id).scalar())
    return {"sidebar": {"stats": [
        ("Courses", mine.count()),
        ("Live", mine.filter(Course.is_published.is_(True)).count()),
        ("Learners", learners or 0),
    ]}}


# ───────────── Helpers ─────────────
def own_course_or_404(course_id):
    return Course.query.filter_by(id=course_id, instructor_id=current_user.id).first_or_404()


def own_section_or_404(section_id):
    return (Section.query.join(Course, Section.course_id == Course.id)
            .filter(Section.id == section_id, Course.instructor_id == current_user.id)
            .first_or_404())


def own_lesson_or_404(lesson_id):
    return (Lesson.query.join(Section, Lesson.section_id == Section.id)
            .join(Course, Section.course_id == Course.id)
            .filter(Lesson.id == lesson_id, Course.instructor_id == current_user.id)
            .first_or_404())


def category_choices():
    return [(0, "No category")] + [(c.id, c.name) for c in Category.query.order_by(Category.name)]


def back(default):
    target = request.form.get("next")
    return redirect(target if is_safe_redirect(target) else default)


def next_position(model, **filters):
    column = model.course_id if "course_id" in filters else model.section_id
    top = db.session.query(func.max(model.position)).filter(column == list(filters.values())[0]).scalar()
    return 0 if top is None else top + 1


def swap(items, obj, direction):
    """Move obj one step up or down and renumber the whole list."""
    items = sorted(items, key=lambda x: (x.position, x.id))
    i = items.index(obj)
    j = i - 1 if direction == "up" else i + 1
    if 0 <= j < len(items):
        items[i], items[j] = items[j], items[i]
        for n, item in enumerate(items):
            item.position = n


def apply_thumbnail(course, file):
    """True on success, or when no new file was sent."""
    if not isinstance(file, FileStorage) or not file.filename:
        return True                       # nothing new uploaded, keep the current image
    try:
        filename = save_picture(file, "course_thumbnails", size=(1280, 720))
    except (OSError, ValueError):
        flash("That image couldn't be processed. Try a different file.", "danger")
        return False
    delete_picture(course.thumbnail, "course_thumbnails")
    course.thumbnail = filename
    return True


# ───────────── Dashboard ─────────────
@instructor.route("/")
def dashboard():
    title = "Instructor's Dashboard || CourseHub"
    courses = (Course.query.filter_by(instructor_id=current_user.id)
               .options(selectinload(Course.sections).selectinload(Section.lessons)).all())
    ids = [c.id for c in courses]
    learners = (db.session.query(func.count(Enrollment.id))
                .filter(Enrollment.course_id.in_(ids)).scalar() if ids else 0)
    recent = (Enrollment.query.join(Course, Enrollment.course_id == Course.id)
              .filter(Course.instructor_id == current_user.id)
              .options(joinedload(Enrollment.student), joinedload(Enrollment.course))
              .order_by(Enrollment.enrolled_at.desc()).limit(6).all())
    stats = {
        "courses": len(courses),
        "published": sum(1 for c in courses if c.is_published),
        "learners": learners or 0,
        "lessons": sum(c.lesson_count for c in courses),
    }
    return render_template("instructor/dashboard.html", stats=stats, recent=recent, title=title)


# Courses 
@instructor.route("/courses")
def courses():
    title = "Instructor Courses || CourseHub"
    status = request.args.get("status", "")
    query = (Course.query.filter_by(instructor_id=current_user.id)
             .options(joinedload(Course.category), selectinload(Course.enrollments),
                      selectinload(Course.sections).selectinload(Section.lessons)))
    if status == "published":
        query = query.filter(Course.is_published.is_(True))
    elif status == "draft":
        query = query.filter(Course.is_published.is_(False))
    rows = query.order_by(Course.created_at.desc()).all()
    return render_template("instructor/courses.html", courses=rows, status=status, title=title)

# Add New Courses 
@instructor.route("/courses/new", methods=["GET", "POST"])
def new_course():
    title = "Instructor Add-Courses || CourseHub"
    form = CourseForm()
    form.category_id.choices = category_choices()
    if form.validate_on_submit():
        course = Course(
            title=form.title.data.strip(),
            description=(form.description.data or "").strip() or None,
            level=form.level.data,
            category_id=form.category_id.data or None,
            instructor_id=current_user.id,
            is_published=False,
        )
        if apply_thumbnail(course, form.thumbnail.data):
            db.session.add(course)
            db.session.commit()
            flash("Course created as a draft. Add some lessons next.", "success")
            return redirect(url_for("instructor.curriculum", course_id=course.id))
    return render_template("instructor/course_form.html", form=form, course=None, title=title)

# Edit Courses
@instructor.route("/courses/<int:course_id>/edit", methods=["GET", "POST"])
def edit_course(course_id):
    title = "Instructor Edit-Courses || CourseHub"
    course = own_course_or_404(course_id)
    form = CourseForm(obj=course)
    form.category_id.choices = category_choices()
    if request.method == "GET":
        form.category_id.data = course.category_id or 0

    if form.validate_on_submit():
        course.title = form.title.data.strip()
        course.description = (form.description.data or "").strip() or None
        course.level = form.level.data
        course.category_id = form.category_id.data or None
        if apply_thumbnail(course, form.thumbnail.data):
            db.session.commit()
            flash("Course details saved.", "success")
            return redirect(url_for("instructor.edit_course", course_id=course.id))
        db.session.rollback()
    return render_template("instructor/course_form.html", form=form, course=course, title=title)

# Publish Courses 
@instructor.route("/courses/<int:course_id>/publish", methods=["POST"])
def toggle_publish(course_id):
    course = own_course_or_404(course_id)
    if not course.is_published and course.lesson_count == 0:
        flash("Add at least one lesson before publishing.", "warning")
    else:
        course.is_published = not course.is_published
        db.session.commit()
        flash(f"'{course.title}' is now {'published' if course.is_published else 'unpublished'}.", "success")
    return back(url_for("instructor.courses"))

# Delete Courses 
@instructor.route("/courses/<int:course_id>/delete", methods=["POST"])
def delete_course(course_id):
    course = own_course_or_404(course_id)
    if course.enrollment_count:
        flash("This course has learners enrolled. Unpublish it instead of deleting it.", "warning")
        return redirect(url_for("instructor.edit_course", course_id=course.id))
    thumbnail = course.thumbnail
    db.session.delete(course)
    db.session.commit()
    delete_picture(thumbnail, "course_thumbnails")
    flash("Course deleted.", "success")
    return redirect(url_for("instructor.courses"))


# ───────────── Curriculum: sections ─────────────
@instructor.route("/courses/<int:course_id>/curriculum")
def curriculum(course_id):
    course = (Course.query.filter_by(id=course_id, instructor_id=current_user.id)
              .options(selectinload(Course.sections).selectinload(Section.lessons))
              .first_or_404())
    return render_template("instructor/curriculum.html", course=course, section_form=SectionForm())


@instructor.route("/courses/<int:course_id>/sections", methods=["POST"])
def add_section(course_id):
    course = own_course_or_404(course_id)
    form = SectionForm()
    if form.validate_on_submit():
        db.session.add(Section(course_id=course.id, title=form.title.data.strip(),
                               position=next_position(Section, course_id=course.id)))
        db.session.commit()
        flash("Section added.", "success")
    else:
        flash(next(iter(form.title.errors), "Couldn't add that section."), "danger")
    return redirect(url_for("instructor.curriculum", course_id=course.id))


@instructor.route("/sections/<int:section_id>/rename", methods=["POST"])
def rename_section(section_id):
    section = own_section_or_404(section_id)
    form = SectionForm()
    if form.validate_on_submit():
        section.title = form.title.data.strip()
        db.session.commit()
        flash("Section renamed.", "success")
    else:
        flash(next(iter(form.title.errors), "Couldn't rename that section."), "danger")
    return redirect(url_for("instructor.curriculum", course_id=section.course_id))


@instructor.route("/sections/<int:section_id>/move", methods=["POST"])
def move_section(section_id):
    section = own_section_or_404(section_id)
    swap(section.course.sections, section, request.form.get("direction"))
    db.session.commit()
    return redirect(url_for("instructor.curriculum", course_id=section.course_id))


@instructor.route("/sections/<int:section_id>/delete", methods=["POST"])
def delete_section(section_id):
    section = own_section_or_404(section_id)
    course_id = section.course_id
    db.session.delete(section)
    db.session.commit()
    flash("Section deleted.", "success")
    return redirect(url_for("instructor.curriculum", course_id=course_id))


# ───────────── Curriculum: lessons ─────────────
@instructor.route("/sections/<int:section_id>/lessons/new", methods=["GET", "POST"])
def new_lesson(section_id):
    section = own_section_or_404(section_id)
    form = LessonForm()
    if form.validate_on_submit():
        video = (form.video_url.data or "").strip()
        db.session.add(Lesson(
            section_id=section.id,
            title=form.title.data.strip(),
            video_url=to_embed_url(video) if video else None,
            body=(form.body.data or "").strip() or None,
            position=next_position(Lesson, section_id=section.id),
        ))
        db.session.commit()
        flash("Lesson added.", "success")
        return redirect(url_for("instructor.curriculum", course_id=section.course_id))
    return render_template("instructor/lesson_form.html", form=form, section=section,
                           course=section.course, lesson=None)


@instructor.route("/lessons/<int:lesson_id>/edit", methods=["GET", "POST"])
def edit_lesson(lesson_id):
    lesson = own_lesson_or_404(lesson_id)
    form = LessonForm(obj=lesson)
    if form.validate_on_submit():
        video = (form.video_url.data or "").strip()
        lesson.title = form.title.data.strip()
        lesson.video_url = to_embed_url(video) if video else None
        lesson.body = (form.body.data or "").strip() or None
        db.session.commit()
        flash("Lesson saved.", "success")
        return redirect(url_for("instructor.curriculum", course_id=lesson.section.course_id))
    return render_template("instructor/lesson_form.html", form=form, section=lesson.section,
                           course=lesson.section.course, lesson=lesson)


@instructor.route("/lessons/<int:lesson_id>/move", methods=["POST"])
def move_lesson(lesson_id):
    lesson = own_lesson_or_404(lesson_id)
    swap(lesson.section.lessons, lesson, request.form.get("direction"))
    db.session.commit()
    return redirect(url_for("instructor.curriculum", course_id=lesson.section.course_id))


@instructor.route("/lessons/<int:lesson_id>/delete", methods=["POST"])
def delete_lesson(lesson_id):
    lesson = own_lesson_or_404(lesson_id)
    course_id = lesson.section.course_id
    db.session.delete(lesson)
    db.session.commit()
    flash("Lesson deleted.", "success")
    return redirect(url_for("instructor.curriculum", course_id=course_id))


# ───────────── Students ─────────────
@instructor.route("/courses/<int:course_id>/students")
def students(course_id):
    course = (Course.query.filter_by(id=course_id, instructor_id=current_user.id)
              .options(selectinload(Course.sections).selectinload(Section.lessons))
              .first_or_404())
    enrollments = (Enrollment.query.filter_by(course_id=course.id)
                   .options(joinedload(Enrollment.student), selectinload(Enrollment.progress))
                   .order_by(Enrollment.enrolled_at.desc()).all())
    return render_template("instructor/students.html", course=course, enrollments=enrollments)