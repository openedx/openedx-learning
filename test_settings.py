"""
These settings are here to use during tests, because django requires them.

In a real-world use case, apps in this project are installed into other
Django applications, so these settings will not be used.
"""

from os.path import abspath, dirname, join


def root(*args):
    """
    Get the absolute path of the given path relative to the project root.
    """
    return join(abspath(dirname(__file__)), *args)


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "default.db",
        "USER": "",
        "PASSWORD": "",
        "HOST": "",
        "PORT": "",
    }
}

# If you provision the 'oel'@'%' with broad permissions on your MySQL instance,
# running the tests will auto-generate a database for running tests. This is
# slower than the default sqlite3 setup above, but it's sometimes helpful for
# finding things that only break in CI.
#
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.mysql",
#         "USER": "oel",
#         "PASSWORD": "oel-test-pass",
#         "HOST": "mysql",
#         "PORT": "3306",
#     }
# }

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    # Admin
    'django.contrib.admin',
    'django.contrib.admindocs',
    # Debugging
    "debug_toolbar",
    # django-rules based authorization
    'rules.apps.AutodiscoverRulesConfig',
    # Our own apps
    "openedx_learning.apps.authoring.collections",
    "openedx_learning.apps.authoring.components",
    "openedx_learning.apps.authoring.media",
    "openedx_learning.apps.authoring.publishing",
    "openedx_tagging.core.tagging",
    "openedx_learning.apps.authoring.sections",
    "openedx_learning.apps.authoring.subsections",
    "openedx_learning.apps.authoring.units",
    "openedx_learning.apps.authoring.backup_restore",
]

AUTHENTICATION_BACKENDS = [
    'rules.permissions.ObjectPermissionBackend',
]

LOCALE_PATHS = [
    root("openedx_learning", "conf", "locale"),
]

ROOT_URLCONF = "projects.urls"

SECRET_KEY = "insecure-secret-key"

USE_TZ = True

MEDIA_ROOT = root("test_media")

######################### Django Rest Framework ########################

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'edx_rest_framework_extensions.paginators.DefaultPagination',
    'PAGE_SIZE': 10,
}

######################## LEARNING CORE SETTINGS ########################

OPENEDX_LEARNING = {
    'MEDIA': {
        'BACKEND': 'django.core.files.storage.InMemoryStorage',
        'OPTIONS': {
            'location': MEDIA_ROOT + "_private"
        }
    }
}

STATIC_URL = 'static/'
