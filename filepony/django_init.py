import django
import os


def setup():
    # Django initialization (must precede any Django-related imports):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "projects.dev")
    django.setup()
