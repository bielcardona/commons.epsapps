SECRET_KEY = 'tests'
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'eps_commons',
]
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'eps_commons.middleware.CurrentUserMiddleware',
    'eps_commons.middleware.CurrentRolMiddleware',
]
ROOT_URLCONF = 'tests.urls'
USE_TZ = True
OAUTH2_CLIENT_ID = 'client'
OAUTH2_CLIENT_SECRET = 'secret'
OAUTH2_TOKEN_URL = 'https://hub.example/token'
OAUTH2_AUTHORIZATION_URL = 'https://hub.example/authorize'
OAUTH2_USERINFO_URL = 'https://hub.example/userinfo'
LOGIN_REDIRECT_URL = '/'
