import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 180,
        'pool_timeout': 10,
        'pool_size': 2,
        'max_overflow': 1,
    }
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    APP_NAME = "Nkuna Banking"
    UNDO_MINUTES = 15
    MAX_DEPOSIT = 50000
    MIN_DEPOSIT = 10
    TRANSFER_FEE_PERCENT = 1.0
    UTILITY_FEE_FIXED = 5.0
    MIN_TRANSFER_FEE = 5.0
    MAX_TRANSFER_FEE = 50.0
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', '1', 'yes']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'shichabonkuna22@gmail.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'dqlb vnee uomu ztei'
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'shichabonkuna22@gmail.com'
    CHAT_HISTORY_LIMIT = int(os.environ.get('CHAT_HISTORY_LIMIT') or 50)

    @staticmethod
    def init_app(app):
        pass

class DevelopmentConfig(Config):
    DEBUG = True
    basedir = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'bank.db')

class ProductionConfig(Config):
    DEBUG = False
    
    # Get database URL from environment or use hardcoded fallback
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        database_url = 'postgresql://bakerslovers:ymTgQWC57PTko8iD1Kg1iE9xQKfIyna5@dpg-d5r6faf5r7bs7390vel0-a/bakerslovers'
    
    # psycopg uses postgresql+psycopg:// format
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql+psycopg://', 1)
    elif database_url.startswith('postgresql://'):
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
    
    SQLALCHEMY_DATABASE_URI = database_url
    
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 180,
        'pool_timeout': 10,
        'pool_size': 2,
        'max_overflow': 1,
    }

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}