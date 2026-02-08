import os
from datetime import timedelta

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Connection pool settings - will be overridden in production
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_timeout': 30,
        'pool_size': 10,
        'max_overflow': 20
    }
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    
    # Application settings
    APP_NAME = "Nkuna Banking"
    UNDO_MINUTES = 15
    MAX_DEPOSIT = 50000
    MIN_DEPOSIT = 10
    
    # Fee configuration
    TRANSFER_FEE_PERCENT = 1.0
    UTILITY_FEE_FIXED = 5.0
    MIN_TRANSFER_FEE = 5.0
    MAX_TRANSFER_FEE = 50.0
    
    # Mail settings
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', '1', 'yes']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'shichabonkuna22@gmail.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'dqlb vnee uomu ztei'
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'shichabonkuna22@gmail.com'
    
    # Chat settings
    CHAT_HISTORY_LIMIT = int(os.environ.get('CHAT_HISTORY_LIMIT') or 50)
    
    @staticmethod
    def init_app(app):
        pass

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    basedir = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'bank.db')

class ProductionConfig(Config):
    """Production configuration for Render"""
    DEBUG = False
    
    # CRITICAL FIX: Use __init__ to delay DATABASE_URL check until instantiation
    def __init__(self):
        # Get DATABASE_URL from environment
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url:
            # Handle both postgres:// and postgresql:// formats
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
            self.SQLALCHEMY_DATABASE_URI = database_url
            
            # Override engine options for Render free tier
            self.SQLALCHEMY_ENGINE_OPTIONS = {
                'pool_pre_ping': True,
                'pool_recycle': 180,     # 3 minutes
                'pool_timeout': 10,
                'pool_size': 2,          # Render free tier: max 10 connections total
                'max_overflow': 1,       # Keep it low
            }
        else:
            raise ValueError("DATABASE_URL environment variable is required for production!")

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}