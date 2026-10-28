import os
import secrets
from urllib.parse import urlparse, urljoin, parse_qs

from flask import current_app, request
from PIL import Image, UnidentifiedImageError

ALLOWED_IMAGES = {"png", "jpg", "jpeg", "webp"}


# ───────────── Uploads ─────────────
def allowed_file(filename, allowed=ALLOWED_IMAGES):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


def save_picture(file, folder, size=(400, 400)):
    """Save an uploaded image to static/uploads/<folder>/ under a random name,
    resized to fit inside `size`. Returns the new filename."""
    if not hasattr(file, "filename") or not file.filename:
        raise ValueError("No file was uploaded.")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext.lstrip(".") not in ALLOWED_IMAGES:
        raise ValueError("Unsupported image type.")

    try:
        file.seek(0)
        with Image.open(file) as img:
            img.verify()
        file.seek(0)
        with Image.open(file) as img:
            img.thumbnail(size)
            if ext in (".jpg", ".jpeg") and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            filename = secrets.token_hex(8) + ext
            folder_path = os.path.join(current_app.root_path, "static", "uploads", folder)
            os.makedirs(folder_path, exist_ok=True)
            img.save(os.path.join(folder_path, filename))
    except (OSError, ValueError, Image.DecompressionBombError, UnidentifiedImageError) as exc:
        raise ValueError("The uploaded file is not a valid image.") from exc

    return filename



def delete_picture(filename, folder, keep=("default.jpg",)):
    """Remove an old upload from disk (never the default image)."""
    if not filename or filename in keep:
        return
    path = os.path.join(current_app.root_path, "static", "uploads", folder, filename)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            current_app.logger.warning("Could not delete uploaded file: %s", path)


# ───────────── Video links ─────────────
def to_embed_url(url):
    """Turn a YouTube or Vimeo link into a safe embed URL.
    Returns None if the link isn't from an allowed site."""
    try:
        parsed = urlparse(url.strip())
    except (ValueError, AttributeError):
        return None
    host = (parsed.hostname or "").lower().removeprefix("www.")

    if host == "youtu.be":
        vid = parsed.path.lstrip("/")
    elif host in ("youtube.com", "m.youtube.com"):
        if parsed.path == "/watch":
            vid = parse_qs(parsed.query).get("v", [""])[0]
        elif parsed.path.startswith("/embed/"):
            vid = parsed.path.split("/embed/")[1]
        else:
            return None
    elif host == "vimeo.com" and parsed.path.strip("/").isdigit():
        return f"https://player.vimeo.com/video/{parsed.path.strip('/')}"
    elif host == "player.vimeo.com" and parsed.path.startswith("/video/"):
        video_id = parsed.path.split("/video/")[1].split("/")[0]
        return f"https://player.vimeo.com/video/{video_id}" if video_id.isdigit() else None
    else:
        return None

    if vid and vid.replace("-", "").replace("_", "").isalnum():
        return f"https://www.youtube.com/embed/{vid}"
    return None


# ───────────── Course player ─────────────
def get_adjacent_lessons(course, lesson):
    """Return (previous, next) lessons in the course's order, or None at the ends."""
    ordered = [l for s in course.sections for l in s.lessons]
    i = ordered.index(lesson)
    prev_lesson = ordered[i - 1] if i > 0 else None
    next_lesson = ordered[i + 1] if i < len(ordered) - 1 else None
    return prev_lesson, next_lesson


# ───────────── Redirect safety ─────────────
def is_safe_redirect(target):
    """True only for same-site URLs. Use it on the `next` parameter after login."""
    if not target:
        return False
    ref = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    return test.scheme in ("http", "https") and ref.netloc == test.netloc