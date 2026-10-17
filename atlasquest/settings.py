import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
ON_VERCEL = os.environ.get("VERCEL") == "1"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if ON_VERCEL:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY in the Vercel project environment.")
    SECRET_KEY = "development-only-atlas-quest-key"
DEBUG = os.environ.get("DJANGO_DEBUG", "0" if ON_VERCEL else "1") == "1"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]", ".vercel.app"]
for host in (
    os.environ.get("VERCEL_URL"),
    os.environ.get("VERCEL_PROJECT_PRODUCTION_URL"),
    *os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(","),
):
    if host:
        ALLOWED_HOSTS.append(host.strip().removeprefix("https://").removeprefix("http://").split("/")[0])


def _database_from_url(database_url):
    parsed = urlsplit(database_url)
    if parsed.scheme not in {"postgres", "postgresql", "postgresql+psycopg"}:
        raise ImproperlyConfigured("DATABASE_URL must be a PostgreSQL connection URL.")
    if not parsed.hostname or not parsed.path.lstrip("/"):
        raise ImproperlyConfigured("DATABASE_URL must include a PostgreSQL host and database name.")
    options = {
        key: values[-1]
        for key, values in parse_qs(parsed.query, keep_blank_values=True).items()
    }
    options.setdefault("sslmode", "require")
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname,
        "PORT": parsed.port or "",
        "CONN_MAX_AGE": 0,
        "OPTIONS": options,
    }

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "game.apps.GameConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]

ROOT_URLCONF = "atlasquest.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

WSGI_APPLICATION = "atlasquest.wsgi.application"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
if DATABASE_URL:
    DATABASES["default"] = _database_from_url(DATABASE_URL)
elif ON_VERCEL:
    raise ImproperlyConfigured(
        "Set DATABASE_URL to a persistent PostgreSQL database in the Vercel project environment."
    )

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = ON_VERCEL
CSRF_COOKIE_SECURE = ON_VERCEL
if ON_VERCEL:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
