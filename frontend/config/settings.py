# config/settings.py
import os
from pathlib import Path
from dotenv import load_dotenv

# تحميل متغيرات البيئة من ملف .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "local-development-only-core-key-change-before-production")
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost,testserver").split(",")
if os.getenv("APP_ENV", "development").lower() == "production":
    from django.core.exceptions import ImproperlyConfigured
    if not os.getenv("DJANGO_SECRET_KEY") or len(SECRET_KEY) < 32 or DEBUG:
        raise ImproperlyConfigured("Production requires a private DJANGO_SECRET_KEY and DJANGO_DEBUG=false")
    if not os.getenv("DJANGO_ALLOWED_HOSTS") or "*" in ALLOWED_HOSTS:
        raise ImproperlyConfigured("Production requires explicit DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    'modules.module_organizations',
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_htmx",
    "crispy_forms",
    "crispy_tailwind",
    "core",
    "modules.module_auth",

    'modules.module_settings',
    "modules.module_users",
    "modules.module_notifications",
    "modules.module_pm",
    "modules.module_daily_work",
    "modules.module_equipment",
    "modules.module_hr",
    "modules.module_inventory",
    'modules.module_audit',  # 🆕 وحدة التدقيق والمتابعة

]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "core.middleware.AuthMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "shared" / "templates", BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "core.context_processors.platform_context",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.getenv("DJANGO_DATABASE_PATH", str(BASE_DIR / "db.sqlite3")),
    }
}

AUTH_USER_MODEL = "core.User"
LOGIN_URL = "/auth/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/auth/login/"

LANGUAGE_CODE = "ar"
TIME_ZONE = "Asia/Riyadh"
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "shared" / "static", BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
WHITENOISE_USE_FINDERS = os.getenv("APP_ENV", "development").lower() != "production"
WHITENOISE_AUTOREFRESH = WHITENOISE_USE_FINDERS
WHITENOISE_MIMETYPES = {".ttf": "font/ttf", ".woff2": "font/woff2"}

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", str(BASE_DIR / "media")))
UPLOAD_ROOT = Path(os.getenv("UPLOAD_ROOT", str(MEDIA_ROOT)))

LOCALE_PATHS = [BASE_DIR / "locale_files"]

CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"

HTMX = {"AUTO_REFRESH": True, "AUTO_RETRY": True, "RETRY_DELAY": 1000}

# ⚡ استخدام متغير البيئة أو القيمة الافتراضية 8001
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8001/api/v1")
WEBSOCKET_URL = os.getenv('WEBSOCKET_URL', 'ws://127.0.0.1:8000/ws/')
WEBSOCKET_URL = os.getenv('WEBSOCKET_URL', 'ws://127.0.0.1:8000/ws/')

SYSTEM_CONFIG = {
    "ITEMS_PER_PAGE": 20,
    "MAX_UPLOAD_SIZE": 10485760,
    "ALLOWED_EXTENSIONS": [".pdf", ".doc", ".docx", ".xlsx", ".jpg", ".png"],
    "DATE_FORMAT": "%Y-%m-%d",
    "DATETIME_FORMAT": "%Y-%m-%d %H:%M:%S",
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"





SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_AGE = 600
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
