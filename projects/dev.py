"""

"""
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / {dir_name} /
BASE_DIR = Path(__file__).resolve().parents[1]


DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "dev.db",
        "USER": "",
        "PASSWORD": "",
        "HOST": "",
        "PORT": "",
    }
}

INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    # Admin
    "django.contrib.admin",
    "django.contrib.admindocs",
    # Learning Core Apps
    "openedx_learning.core.components.apps.ComponentsConfig",
    "openedx_learning.core.publishing.apps.PublishingConfig",
    # Learning Contrib Apps
    "openedx_learning.contrib.media_server.apps.MediaServerConfig",
    # Apps that don't belong in this repo in the long term, but are here to make
    # testing/iteration easier until the APIs stabilize.
    "olx_importer.apps.OLXImporterConfig",
    # REST API
    "rest_framework",
    "openedx_learning.rest_api.apps.RESTAPIConfig",
)

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Admin-specific
    "django.contrib.admindocs.middleware.XViewMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    },
]

LOCALE_PATHS = [
    BASE_DIR / "conf" / "locale",
]

ROOT_URLCONF = "projects.urls"

SECRET_KEY = "insecure-secret-key"

STATIC_URL = "/static/"
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]
STATICFILES_DIRS = [
    #     BASE_DIR / 'projects' / 'static'
]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

USE_TZ = True

# openedx-learning required configuration
OPENEDX_LEARNING = {
    # Custom file storage, though this is better done through Django's
    # STORAGES setting in Django >= 4.2
    "STORAGE": None,
}
