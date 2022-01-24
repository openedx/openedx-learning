"""

"""
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / {dir_name} /
BASE_DIR = Path(__file__).resolve().parents[2]


DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'dev.db',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    }
}

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.sessions',
    'django.contrib.staticfiles',

    # Admin
    'django.contrib.admin',
    'django.contrib.admindocs',

    # Our own apps
    'openedx_learning.apps.learning_publishing.apps.PublishingConfig',
)

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    # Admin-specific
    'django.contrib.admindocs.middleware.XViewMiddleware',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ]
        }
    },
]

LOCALE_PATHS = [
    BASE_DIR / 'openedx_learning' / 'conf' / 'locale',
]

ROOT_URLCONF = 'projects.urls'

SECRET_KEY = 'insecure-secret-key'

STATIC_URL = '/static/'
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]
STATICFILES_DIRS = [
    BASE_DIR / 'projects' / 'static'
]
MEDIA_URL = '/media/'