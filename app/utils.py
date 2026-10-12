import os
import secrets
from flask import current_app, request
from urllib.parse import urlparse, urljoin

def is_safe_redirect(target):
    """True only for same-site URLs. Use it on the `next` parameter after login."""
    if not target:
        return False
    ref = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    return test.scheme in ("http", "https") and ref.netloc == test.netloc