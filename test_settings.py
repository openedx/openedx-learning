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
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'default.db',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    }
}

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.sessions',
    'django.contrib.staticfiles',

    # Admin
#    'django.contrib.admin',
#    'django.contrib.admindocs',

    # Our own apps
    'openedx_learning.core.publishing.apps.PublishingConfig',
    'openedx_learning.core.components.apps.ComponentsConfig',
]

LOCALE_PATHS = [
    root('openedx_learning', 'conf', 'locale'),
]

ROOT_URLCONF = 'projects.urls'

SECRET_KEY = 'insecure-secret-key'

USE_TZ = True
