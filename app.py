import os
import logging
from flask import Flask, render_template, request, jsonify, redirect, url_for, abort, flash
from flask_login import LoginManager, current_user
from flask_mail import Mail, Message
from flask_socketio import SocketIO
from sqlalchemy.exc import OperationalError
import time

from config import config
from models import db, User
from utils import seed_default_fees, format_currency, format_datetime
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

login_manager = LoginManager()
mail = Mail()
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading', logger=False, engineio_logger=False)

def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    app = Flask(__name__, static_folder='static', static_url_path='/static')
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    
    # Ensure static directories exist
    os.makedirs(os.path.join(app.root_path, 'static', 'css'), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, 'static', 'js'), exist_ok=True)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    socketio.init_app(app)
    
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        if user_id is None or user_id == 'None':
            return None
        try:
            return User.query.get(int(user_id))
        except (ValueError, TypeError):
            return None
    
    # Register blueprints
    from auth import auth_bp
    from user_routes import user_bp
    from admin_routes import admin_bp
    from chat_routes import chat_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp, url_prefix='/user')
    app.register_blueprint(admin_bp)
    app.register_blueprint(chat_bp)
    
    # Public endpoints - FIXED: Added admin.login
    PUBLIC_ENDPOINTS = {
        'index', 'about', 'contact', 'auth.login', 'auth.register', 
        'auth.logout', 'static', 'api_verify_account', 'health', 'admin.login'
    }
    
    @app.before_request
    def require_auth():
        if current_user.is_authenticated:
            return None
        if request.endpoint in PUBLIC_ENDPOINTS:
            return None
        if request.path.startswith('/static/'):
            return None
        return redirect(url_for('auth.login', next=request.url))
    
    # CRITICAL: Health check endpoint for Render
    @app.route('/health')
    def health():
        """Health check endpoint - Render uses this to verify app is alive"""
        try:
            # Test database connection
            db.session.execute('SELECT 1')
            return jsonify({'status': 'healthy', 'database': 'connected'}), 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return jsonify({'status': 'unhealthy', 'error': str(e)}), 500
    
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            if getattr(current_user, 'is_admin', False):
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('user.dashboard'))
        return render_template('index.html')
    
    @app.route('/about')
    def about():
        return render_template('about.html')
    
    @app.route('/contact', methods=['GET', 'POST'])
    def contact():
        from forms import ContactForm
        form = ContactForm()
        
        if form.validate_on_submit():
            try:
                msg = Message(
                    subject=f"Nkuna Banking Contact: {form.subject.data}",
                    sender=app.config['MAIL_DEFAULT_SENDER'],
                    recipients=[app.config['MAIL_USERNAME']],
                    reply_to=form.email.data
                )
                
                msg.body = f"""
                New Contact Form Submission - Nkuna Banking
                
                From: {form.full_name.data}
                User Email: {form.email.data}
                Subject: {form.subject.data}
                Date: {datetime.now().strftime('%d %b %Y, %I:%M %p')} (SAST)
                
                Message:
                {form.message.data}
                
                ---
                This email was sent from the Nkuna Banking contact form.
                """
                
                mail.send(msg)
                flash('Your message has been sent successfully!', 'success')
                return redirect(url_for('contact'))
                
            except Exception as e:
                logger.error(f"Failed to send contact form email: {str(e)}")
                flash('Sorry, there was an error sending your message.', 'error')
        
        # CRITICAL FIX: Pass format_currency to template
        return render_template('contact.html', form=form, format_currency=format_currency)
    
    @app.route('/verify_account_api', methods=['POST'])
    def api_verify_account():
        data = request.get_json() or {}
        account_number = data.get('account_number', '')
        if not account_number:
            return jsonify({'success': False, 'message': 'Account number required'})
        if not account_number.isdigit() or len(account_number) != 10:
            return jsonify({'success': False, 'message': 'Account number must be 10 digits'})
        if current_user.is_authenticated and account_number == current_user.account_number:
            return jsonify({'success': False, 'message': 'Cannot transfer to your own account'})
        user = User.query.filter_by(account_number=account_number, is_active=True).first()
        if user:
            return jsonify({'success': True, 'message': f'Account verified: {user.full_name}', 'full_name': user.full_name, 'account_number': user.account_number})
        return jsonify({'success': False, 'message': 'Account not found or inactive'})
    
    @app.errorhandler(404)
    def not_found_error(error):
        return "Page not found", 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        logger.error(f"Internal server error: {error}")
        return "Internal server error", 500
    
    @app.errorhandler(OperationalError)
    def handle_db_error(error):
        db.session.rollback()
        logger.error(f"Database operational error: {error}")
        flash('Database connection error. Please try again.', 'error')
        return redirect(url_for('index'))
    
    @app.context_processor
    def inject_now():
        return {'now': datetime.now()}
    
    @app.context_processor
    def inject_user():
        return {'current_user': current_user}
    
    # CRITICAL FIX: Add format_currency and format_datetime to all templates globally
    @app.context_processor
    def inject_utils():
        return {
            'format_currency': format_currency,
            'format_datetime': format_datetime
        }
    
    @app.context_processor
    def inject_config():
        from config import Config
        return {'config': Config}
    
    @app.template_filter('datetimeformat')
    def datetimeformat_filter(value, format='%d %b %Y, %I:%M %p'):
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.strftime(format)
        return value
    
    # CRITICAL FIX: Only run database setup ONCE using a file lock
    # This prevents multiple gunicorn workers from conflicting during startup
    with app.app_context():
        try:
            # Check if tables exist by trying to query User
            try:
                User.query.first()
                tables_exist = True
            except:
                tables_exist = False
            
            if not tables_exist:
                logger.info("Creating database tables...")
                db.create_all()
                seed_default_fees()
                
                # Create admin user only if not exists
                admin = User.query.filter_by(email='admin@nkunabank.co.za').first()
                if not admin:
                    admin = User(
                        full_name='System Administrator',
                        email='admin@nkunabank.co.za',
                        id_number='0000000000000',
                        phone='0000000000',
                        account_number='0000000000',
                        is_admin=True,
                        is_active=True
                    )
                    admin.set_password('admin123')
                    db.session.add(admin)
                    db.session.commit()
                    logger.info("Default admin user created")
            else:
                logger.info("Database tables already exist, skipping creation")
                
        except Exception as e:
            logger.error(f"Error during database initialization: {e}")
            db.session.rollback()
    
    return app

# Create app instance
app = create_app()

# Register SocketIO handlers
from chat_routes import register_socketio_handlers
register_socketio_handlers(socketio)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1', 'yes']
    socketio.run(app, host='0.0.0.0', port=port, debug=debug_mode)