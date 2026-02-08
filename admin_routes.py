from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user, login_user, logout_user
from functools import wraps
from datetime import datetime, timedelta
from models import db, User, Transaction, FinancialGoal, AdminFeeConfig
from forms import AdminLoginForm
from utils import get_system_stats, format_currency, format_datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not getattr(current_user, 'is_admin', False):
            flash('Admin access required.', 'error')
            return redirect(url_for('user.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login"""
    if current_user.is_authenticated and getattr(current_user, 'is_admin', False):
        return redirect(url_for('admin.dashboard'))
    
    form = AdminLoginForm()
    
    if form.validate_on_submit():
        if form.username.data == 'admin' and form.password.data == 'admin123':
            admin_user = User.query.filter_by(email='admin@nkunabank.co.za').first()
            
            if not admin_user:
                admin_user = User(
                    full_name='System Administrator',
                    email='admin@nkunabank.co.za',
                    id_number='0000000000000',
                    phone='0000000000',
                    account_number='0000000000',
                    is_admin=True,
                    is_active=True
                )
                admin_user.set_password('admin123')
                db.session.add(admin_user)
                db.session.commit()
            
            login_user(admin_user, remember=True)
            flash('Admin login successful!', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Invalid admin credentials.', 'error')
    
    return render_template('admin/login.html', form=form)

@admin_bp.route('/')
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Admin dashboard"""
    stats = get_system_stats()
    return render_template('admin/dashboard.html',
        stats=stats,
        format_currency=format_currency,
        format_datetime=format_datetime
    )

@admin_bp.route('/users')
@admin_required
def users():
    """Manage users"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    search = request.args.get('search', '')
    
    query = User.query
    
    if search:
        query = query.filter(
            (User.full_name.ilike(f'%{search}%')) |
            (User.account_number.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%'))
        )
    
    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin/users.html',
        users=users,
        search=search,
        format_currency=format_currency
    )

@admin_bp.route('/user/<int:user_id>')
@admin_required
def user_detail(user_id):
    """View user details"""
    user = User.query.get_or_404(user_id)
    
    transactions = Transaction.query.filter_by(
        user_id=user_id
    ).order_by(
        Transaction.created_at.desc()
    ).limit(20).all()
    
    goals = FinancialGoal.query.filter_by(
        user_id=user_id
    ).all()
    
    return render_template('admin/user_detail.html',
        user=user,
        transactions=transactions,
        goals=goals,
        format_currency=format_currency,
        format_datetime=format_datetime
    )

@admin_bp.route('/user/<int:user_id>/toggle_status', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    """Activate/Deactivate user"""
    user = User.query.get_or_404(user_id)
    
    if user.is_admin:
        flash('Cannot deactivate admin users.', 'error')
        return redirect(url_for('admin.user_detail', user_id=user_id))
    
    user.is_active = not user.is_active
    status = 'activated' if user.is_active else 'deactivated'
    
    try:
        db.session.commit()
        flash(f'User {status} successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Failed to update user status.', 'error')
    
    return redirect(url_for('admin.user_detail', user_id=user_id))

@admin_bp.route('/transactions')
@admin_required
def transactions():
    """View all transactions"""
    page = request.args.get('page', 1, type=int)
    per_page = 30
    transaction_type = request.args.get('type', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    query = Transaction.query
    
    if transaction_type:
        query = query.filter_by(transaction_type=transaction_type)
    
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Transaction.created_at >= start)
        except ValueError:
            pass
    
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Transaction.created_at < end)
        except ValueError:
            pass
    
    transactions = query.order_by(Transaction.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    type_counts = {}
    for ttype in ['deposit', 'transfer', 'utility', 'goal_deposit', 'goal_withdrawal', 'reversal']:
        count = Transaction.query.filter_by(transaction_type=ttype).count()
        type_counts[ttype] = count
    
    return render_template('admin/transactions.html',
        transactions=transactions,
        type_counts=type_counts,
        format_currency=format_currency,
        format_datetime=format_datetime
    )

@admin_bp.route('/fees', methods=['GET', 'POST'])
@admin_required
def fees():
    """Manage fee configuration"""
    fee_configs = AdminFeeConfig.query.order_by(AdminFeeConfig.applies_to_transaction_type).all()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update':
            fee_id = request.form.get('fee_id')
            fee = AdminFeeConfig.query.get(fee_id)
            
            if fee:
                try:
                    fee.fee_percentage = float(request.form.get('fee_percentage', 0))
                    fee.minimum_fee = float(request.form.get('minimum_fee', 0))
                    max_fee = request.form.get('maximum_fee')
                    fee.maximum_fee = float(max_fee) if max_fee and max_fee.strip() else None
                    fee.is_active = 'is_active' in request.form
                    fee.updated_at = datetime.now()
                    
                    db.session.commit()
                    flash('Fee configuration updated successfully.', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash('Failed to update fee configuration.', 'error')
        
        elif action == 'toggle':
            fee_id = request.form.get('fee_id')
            fee = AdminFeeConfig.query.get(fee_id)
            
            if fee:
                fee.is_active = not fee.is_active
                fee.updated_at = datetime.now()
                
                try:
                    db.session.commit()
                    status = 'enabled' if fee.is_active else 'disabled'
                    flash(f'Fee {status} successfully.', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash('Failed to update fee status.', 'error')
        
        return redirect(url_for('admin.fees'))
    
    return render_template('admin/fees.html', fee_configs=fee_configs)

@admin_bp.route('/force_reverse/<int:transaction_id>', methods=['POST'])
@admin_required
def force_reverse(transaction_id):
    """Force reverse any transaction (admin override)"""
    transaction = Transaction.query.get_or_404(transaction_id)
    
    if transaction.status == 'reversed':
        flash('Transaction is already reversed.', 'error')
        return redirect(url_for('admin.transactions'))
    
    try:
        reversal = Transaction(
            user_id=transaction.user_id,
            transaction_type='reversal',
            amount=transaction.amount,
            reference=f'Admin reversal of {transaction.transaction_type}',
            status='completed',
            original_transaction_id=transaction.id
        )
        
        transaction.status = 'reversed'
        
        user = User.query.get(transaction.user_id)
        
        if transaction.transaction_type == 'deposit':
            user.balance -= transaction.amount
        elif transaction.transaction_type in ['transfer', 'utility']:
            user.balance += transaction.amount
        
        db.session.add(reversal)
        db.session.commit()
        
        flash('Transaction force reversed successfully.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Failed to reverse transaction.', 'error')
    
    return redirect(url_for('admin.transactions'))

@admin_bp.route('/logout')
@login_required
def logout():
    """Admin logout"""
    logout_user()
    flash('Admin session ended.', 'info')
    return redirect(url_for('admin.login'))