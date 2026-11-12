"""
Django settings for stockapp project.
Loads MySQL credentials and secrets from .env (see .env.example).
"""
from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY is not set. Add it to your .env — generate with:\n"
        "  python -c \"import secrets; print(secrets.token_urlsafe(64))\""
    )

DEBUG = os.getenv("DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

# Production hardening — only kicks in when DEBUG is False
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "True").lower() == "true"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30   # 30 days; bump to 1y after you're sure
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "rest_framework",
    # OAuth / social login
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.apple",
    "allauth.socialaccount.providers.github",
    # Project apps
    "apps.stocks",
    "apps.portfolio",
    "apps.learning",
    "apps.screener",
]

SITE_ID = 1

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# django-allauth config
ACCOUNT_LOGIN_METHODS = {"email", "username"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = os.getenv("ACCOUNT_EMAIL_VERIFICATION", "none")
# Dev-friendly default: print emails to the console instead of SMTP.
# In production, switch to: django.core.mail.backends.smtp.EmailBackend
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "TradeLab <noreply@tradelab.local>")
ACCOUNT_SESSION_REMEMBER = True
LOGIN_REDIRECT_URL = "/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    },
    "github": {"SCOPE": ["user:email"]},
    # Apple: configure client_id, team, key, secret via admin or .env later
}

ROOT_URLCONF = "stockapp.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.stocks.context_processors.search_universe",
                "apps.stocks.context_processors.market_status",
                "apps.stocks.context_processors.oauth_providers",
            ],
            "builtins": [
                "apps.stocks.templatetags.inr",
            ],
        },
    },
]

WSGI_APPLICATION = "stockapp.wsgi.application"

DB_ENGINE = os.getenv("DB_ENGINE", "django.db.backends.mysql")
if DB_ENGINE == "django.db.backends.sqlite3":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            # The dashboard writes the price cache from several threads at
            # once; wait for the lock instead of failing with "database is locked".
            "OPTIONS": {"timeout": 20},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": DB_ENGINE,
            "NAME": os.getenv("DB_NAME", "stockapp_db"),
            "USER": os.getenv("DB_USER", "root"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "3306"),
            # Reuse DB connections across requests (a new TCP+TLS handshake to a
            # hosted database costs 50-100 ms per request otherwise).
            "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
            "CONN_HEALTH_CHECKS": True,
        }
    }
    if DB_ENGINE == "django.db.backends.mysql":
        DATABASES["default"]["OPTIONS"] = {"charset": "utf8mb4"}

# Shared cache for price history, fundamentals and analysis reports.
#   db     — persists across restarts and is shared by all gunicorn workers
#            (run `manage.py createcachetable`; the Procfile release step does).
#   locmem — per-process, lost on restart; fine for a quick local trial.
CACHE_BACKEND = os.getenv("CACHE_BACKEND", "db")
if CACHE_BACKEND == "locmem":
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "tradelab_cache",
            "OPTIONS": {"MAX_ENTRIES": 5000, "CULL_FREQUENCY": 4},
        }
    }

# Keep the dashboard universe warm from a background thread while the
# process is alive, so visitors never wait on a cold Yahoo fetch.
PREWARM_IN_PROCESS = os.getenv("PREWARM_IN_PROCESS", "true").lower() == "true"

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
if not DEBUG:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/accounts/login/"


def _skip_socket_timeout(record):
    # Silence harmless socket.timeout tracebacks from idle keep-alive
    # connections to Django's dev server (runserver).
    exc = getattr(record, "exc_info", None)
    if exc and exc[0] is not None and issubclass(exc[0], (TimeoutError,)):
        return False
    msg = record.getMessage()
    if "socket.timeout" in msg or "timed out" in msg:
        return False
    return True


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "skip_socket_timeout": {
            "()": "django.utils.log.CallbackFilter",
            "callback": _skip_socket_timeout,
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["skip_socket_timeout"],
        },
    },
    "loggers": {
        "django.server": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
