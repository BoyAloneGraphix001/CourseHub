from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import (Course, Section, Lesson, Enrollment, LessonProgress,
                        ProfileUpdate, Report)
from app.student.forms import ProfileForm, ChangePasswordForm, ReportForm
from app.utils import get_adjacent_lessons, save_picture, delete_picture

student = Blueprint("student", __name__)


# ───────────── Sidebar data (available in every student template) ─────────────
@student.context_processor
def sidebar_data():
    if not current_user.is_authenticated:
        return {}
    enrollments = current_user.enrollments
    has_picture = bool(current_user.profile_pic) and current_user.profile_pic != "default.jpg"
    checks = [
        (bool(current_user.bio), "Add a short bio"),
        (has_picture, "Upload a profile picture"),
        (bool(enrollments), "Enroll in a course"),
    ]
    missing = [hint for ok, hint in checks if not ok]
    return {"sidebar": {
        "stats": [
            ("Enrolled", len(enrollments)),
            ("Lessons", sum(len(e.progress) for e in enrollments)),
            ("Finished", sum(1 for e in enrollments if e.progress_percent == 100)),
        ],
        "percent": round(sum(ok for ok, _ in checks) / len(checks) * 100),
        "hint": missing[0] if missing else None,
    }}


def resume_lesson(course, done_ids):
    lessons = [l for s in course.sections for l in s.lessons]
    return next((l for l in lessons if l.id not in done_ids), lessons[0] if lessons else None)


# ───────────── Dashboard ─────────────
@student.route("/dashboard")
@login_required
def dashboard():
    title = "Dashboard || CourseHub"
    enrollments = (
        Enrollment.query.filter_by(student_id=current_user.id)
        .options(
            joinedload(Enrollment.course).joinedload(Course.instructor),
            joinedload(Enrollment.course).joinedload(Course.category),
            joinedload(Enrollment.course).selectinload(Course.sections).selectinload(Section.lessons),
            selectinload(Enrollment.progress),
        )
        .order_by(Enrollment.enrolled_at.desc()).all()
    )
    cont_enrollment, cont_lesson = None, None
    for e in enrollments:
        if (e.course.is_published
                and e.course.instructor.is_active_account
                and e.progress_percent < 100
                and e.course.lesson_count):
            cont_enrollment, cont_lesson = e, resume_lesson(e.course, e.completed_lesson_ids)
            break
    return render_template("student/dashboard.html", enrollments=enrollments,
                           cont_enrollment=cont_enrollment, cont_lesson=cont_lesson, title=title)


# ───────────── Enrol ─────────────
@student.route("/enroll/<int:course_id>", methods=["POST"])
@login_required
def enroll(course_id):
    course = Course.query.filter_by(id=course_id, is_published=True).first_or_404()
    if course.instructor_id == current_user.id:
        flash("This is your own course.", "info")
    elif not course.instructor.is_active_account:
        flash("This course is unavailable because the instructor is suspended.", "warning")
    elif not Enrollment.query.filter_by(student_id=current_user.id, course_id=course.id).first():
        db.session.add(Enrollment(student_id=current_user.id, course_id=course.id))
        db.session.commit()
        flash(f"You are now enrolled in {course.title}. Your lessons are unlocked.", "success")
    return redirect(url_for("main.course_detail", course_id=course.id))


# ───────────── Course player ─────────────
@student.route("/learn/<int:course_id>/<int:lesson_id>")
@login_required
def player(course_id, lesson_id):
    course = (Course.query
              .options(joinedload(Course.instructor),
                       selectinload(Course.sections).selectinload(Section.lessons))
              .filter_by(id=course_id).first_or_404())
    lesson = db.get_or_404(Lesson, lesson_id)
    if lesson.section.course_id != course.id:
        abort(404)                                    # lesson must belong to this course

    enrollment = Enrollment.query.filter_by(
        student_id=current_user.id, course_id=course.id).first()
    is_owner = course.instructor_id == current_user.id
    if not (enrollment or is_owner or current_user.is_admin):
        flash("Enroll in this course to watch its lessons.", "info")
        return redirect(url_for("main.course_detail", course_id=course.id))
    if not course.is_published and not (is_owner or current_user.is_admin):
        abort(404)

    done_ids = enrollment.completed_lesson_ids if enrollment else set()
    prev_lesson, next_lesson = get_adjacent_lessons(course, lesson)
    return render_template("student/player.html", course=course, lesson=lesson,
                           enrollment=enrollment, done_ids=done_ids,
                           prev_lesson=prev_lesson, next_lesson=next_lesson)


@student.route("/lessons/<int:lesson_id>/complete", methods=["POST"])
@login_required
def toggle_complete(lesson_id):
    lesson = db.get_or_404(Lesson, lesson_id)
    enrollment = Enrollment.query.filter_by(
        student_id=current_user.id, course_id=lesson.section.course_id).first_or_404()
    row = LessonProgress.query.filter_by(enrollment_id=enrollment.id, lesson_id=lesson.id).first()
    if row:
        db.session.delete(row)
    else:
        db.session.add(LessonProgress(enrollment_id=enrollment.id, lesson_id=lesson.id))
    db.session.commit()
    return redirect(url_for("student.player", course_id=enrollment.course_id, lesson_id=lesson.id))


# ───────────── Profile ─────────────
@student.route("/profile")
@login_required
def profile():
    title = "Profile || CourseHub"
    updates = (ProfileUpdate.query.filter_by(user_id=current_user.id)
               .order_by(ProfileUpdate.created_at.desc()).limit(20).all())
    return render_template("student/profile.html", updates=updates, title=title)


@student.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    title = "Edit Profile || CourseHub"
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        changes = []
        previous_picture = current_user.profile_pic
        new_picture = None
        username = form.username.data.strip()
        bio = (form.bio.data or "").strip()

        if username != current_user.username:
            current_user.username = username
            changes.append("Username")
        if bio != (current_user.bio or ""):
            current_user.bio = bio
            changes.append("Bio")
        if current_user.is_instructor:
            headline = (form.headline.data or "").strip()
            if headline != (current_user.headline or ""):
                current_user.headline = headline
                changes.append("Headline")
        if form.picture.data:
            try:
                filename = save_picture(form.picture.data, "profile_pics", size=(400, 400))
            except (OSError, ValueError):
                flash("That image couldn't be processed. Try a different file.", "danger")
                return render_template("student/edit_profile.html", form=form,
                                       password_form=ChangePasswordForm())
            new_picture = filename
            current_user.profile_pic = filename
            changes.append("Profile picture")

        if not changes:
            flash("No changes to save.", "info")
            return redirect(url_for("student.profile"))

        for label in changes:
            db.session.add(ProfileUpdate(user_id=current_user.id, summary=f"{label} updated"))
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            if new_picture:
                delete_picture(new_picture, "profile_pics")
            flash("Your profile could not be updated. Please try again.", "danger")
            return redirect(url_for("student.edit_profile"))

        if new_picture and previous_picture != new_picture:
            delete_picture(previous_picture, "profile_pics")

        flash("Profile updated.", "success")
        return redirect(url_for("student.profile"))

    return render_template("student/edit_profile.html", form=form,
                           password_form=ChangePasswordForm(), title=title)


@student.route("/profile/remove-picture", methods=["POST"])
@login_required
def remove_profile_picture():
    previous_picture = current_user.profile_pic
    current_user.profile_pic = "default.jpg"
    db.session.add(ProfileUpdate(user_id=current_user.id, summary="Profile picture removed"))

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash("Your profile picture could not be removed. Please try again.", "danger")
        return redirect(url_for("student.edit_profile"))

    if previous_picture != "default.jpg":
        delete_picture(previous_picture, "profile_pics")

    flash("Profile picture removed. The default image has been restored.", "success")
    return redirect(url_for("student.edit_profile"))


@student.route("/profile/password", methods=["POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Your current password is incorrect.", "danger")
        else:
            current_user.set_password(form.new_password.data)
            db.session.add(ProfileUpdate(user_id=current_user.id, summary="Password changed"))
            db.session.commit()
            flash("Password updated.", "success")
            return redirect(url_for("student.profile"))
    else:
        errors = [e for field_errors in form.errors.values() for e in field_errors]
        flash(errors[0] if errors else "Couldn't update your password.", "danger")
    return redirect(url_for("student.edit_profile"))


@student.route("/become-instructor", methods=["POST"])
@login_required
def become_instructor():
    current_user.is_instructor = True
    db.session.commit()
    flash("Instructor tools are now turned on.", "success")
    return redirect(url_for("instructor.dashboard"))


# ───────────── Report a course ─────────────
@student.route("/report/<int:course_id>", methods=["GET", "POST"])
@login_required
def report_course(course_id):
    course = Course.query.filter_by(id=course_id, is_published=True).first_or_404()
    if course.instructor_id == current_user.id:
        flash("You can't report your own course.", "warning")
        return redirect(url_for("main.course_detail", course_id=course.id))

    form = ReportForm()
    if form.validate_on_submit():
        already = Report.query.filter_by(course_id=course.id, reporter_id=current_user.id,
                                         status="open").first()
        if already:
            flash("You've already reported this course. We'll review it soon.", "info")
        else:
            db.session.add(Report(course_id=course.id, reporter_id=current_user.id,
                                  reason=form.reason.data.strip()))
            db.session.commit()
            flash("Thanks. We'll review your report.", "success")
        return redirect(url_for("main.course_detail", course_id=course.id))
    return render_template("student/report_course.html", form=form, course=course)