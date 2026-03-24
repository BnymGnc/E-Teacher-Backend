import os
from pathlib import Path
from datetime import timedelta
import dj_database_url

# Proje dizin yolları
BASE_DIR = Path(__file__).resolve().parent.parent

# --- GÜVENLİK AYARLARI ---
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-e-teacher-gelistirme-anahtari-12345')
DEBUG = os.environ.get('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = ['*']

# --- UYGULAMALAR ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Bizim Eklediklerimiz
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'api',
    'whitenoise.runserver_nostatic', # Statik dosyalar için eklendi
]


# --- MIDDLEWARE (Sıralama Önemlidir) ---
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', 
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# --- VERİTABANI ---
# Render'da DATABASE_URL varsa onu kullanır, yoksa senin Neon linkini kullanır
DATABASES = {
    'default': dj_database_url.config(
        default='postgresql://neondb_owner:npg_Ww5zUK1TFaXh@ep-restless-math-an3zdlr6-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require',
        conn_max_age=600
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# --- DİL VE SAAT (Türkiye'ye Özel) ---
LANGUAGE_CODE = 'tr-tr'
TIME_ZONE = 'Europe/Istanbul'
USE_I18N = True
USE_TZ = True

# --- STATİK DOSYA AYARLARI (RENDER HATASINI ÇÖZEN KISIM) ---
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
# Statik dosyaların sıkıştırılması için (Whitenoise)
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- BİZİM REACT VE JWT AYARLARIMIZ ---
CORS_ALLOW_ALL_ORIGINS = True 

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}














