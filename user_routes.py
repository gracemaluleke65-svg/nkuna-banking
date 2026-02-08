from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from models import db, User, Transaction, FinancialGoal, Beneficiary
from forms import DepositForm, TransferForm, UtilityPaymentForm, GoalForm, GoalTransactionForm
from utils import (
    format_currency, format_datetime, verify_account, 
    create_transaction, undo_transaction, calculate_transfer_fee, 
    calculate_utility_fee
)

# FIXED: Added url_prefix to avoid route conflicts
user_bp = Blueprint('user', __name__, url_prefix='/user')

@user_bp.route('/')
@user_bp.route('/dashboard')
@login_required
def dashboard():
    """User dashboard"""
    recent_transactions = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Transaction.created_at.desc()
    ).limit(5).all()
    
    active_goals = FinancialGoal.query.filter_by(
        user_id=current_user.id,
        is_completed=False
    ).all()
    
    total_goals_saved = db.session.query(db.func.sum(FinancialGoal.current_amount)).filter_by(
        user_id=current_user.id
    ).scalar() or 0
    
    return render_template('dashboard.html',
        user=current_user,
        recent_transactions=recent_transactions,
        active_goals=active_goals,
        total_goals_saved=total_goals_saved,
        format_currency=format_currency,
        format_datetime=format_datetime
    )    
    

@user_bp.route('/deposit', methods=['GET', 'POST'])
@login_required
def deposit():
    """Deposit money"""
    form = DepositForm()
    
    if form.validate_on_submit():
        amount = float(form.amount.data)
        
        current_user.balance += amount
        
        transaction = create_transaction(
            user_id=current_user.id,
            transaction_type='deposit',
            amount=amount,
            reference='Deposit',
            is_sender=True
        )
        
        try:
            db.session.add(transaction)
            db.session.commit()
            flash(f'Successfully deposited {format_currency(amount)}', 'success')
            return redirect(url_for('user.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('Deposit failed. Please try again.', 'error')
    
    return render_template('deposit.html', form=form, format_currency=format_currency)

@user_bp.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    """Transfer money"""
    form = TransferForm()
    
    if form.validate_on_submit():
        account_number = form.account_number.data
        amount = float(form.amount.data)
        reference = form.reference.data or ''
        
        fee = calculate_transfer_fee(amount)
        total = amount + fee
        
        if not current_user.can_afford(total, include_fee=True):
            flash(f'Insufficient balance. You need {format_currency(total)} (including fee).', 'error')
            return redirect(url_for('user.transfer'))
        
        recipient = User.query.filter_by(
            account_number=account_number,
            is_active=True
        ).first()
        
        if not recipient:
            flash('Recipient account not found or inactive.', 'error')
            return redirect(url_for('user.transfer'))
        
        if recipient.id == current_user.id:
            flash('Cannot transfer to your own account.', 'error')
            return redirect(url_for('user.transfer'))
        
        try:
            current_user.balance -= total
            recipient.balance += amount
            
            # Sender's transaction (money going out)
            sender_transaction = create_transaction(
                user_id=current_user.id,
                transaction_type='transfer',
                amount=amount,
                reference=reference,
                recipient_account_number=recipient.account_number,
                recipient_name=recipient.full_name,
                admin_fee=fee,
                is_sender=True,  # This user initiated the transfer
                sender_account_number=current_user.account_number,
                sender_name=current_user.full_name
            )
            
            # Receiver's transaction (money coming in)
            recipient_transaction = create_transaction(
                user_id=recipient.id,
                transaction_type='transfer',
                amount=amount,
                reference=f'From {current_user.full_name}: {reference}' if reference else f'From {current_user.full_name}',
                recipient_account_number=current_user.account_number,
                recipient_name=current_user.full_name,
                is_sender=False,  # This user did NOT initiate the transfer
                sender_account_number=current_user.account_number,
                sender_name=current_user.full_name
            )
            
            db.session.add(sender_transaction)
            db.session.add(recipient_transaction)
            db.session.commit()
            
            flash(f'Successfully transferred {format_currency(amount)} to {recipient.full_name}. Fee: {format_currency(fee)}', 'success')
            return redirect(url_for('user.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash('Transfer failed. Please try again.', 'error')
    
    return render_template('transfer.html', form=form, format_currency=format_currency)

@user_bp.route('/utilities', methods=['GET', 'POST'])
@login_required
def utilities():
    """Pay utilities"""
    form = UtilityPaymentForm()
    
    if form.validate_on_submit():
        service_type = form.service_type.data
        account_number = form.account_number.data
        amount = float(form.amount.data)
        
        fee = calculate_utility_fee()
        total = amount + fee
        
        if not current_user.can_afford(total, include_fee=True):
            flash(f'Insufficient balance. You need {format_currency(total)} (including fee).', 'error')
            return redirect(url_for('user.utilities'))
        
        service_names = {
            'airtime': 'Airtime',
            'data': 'Mobile Data',
            'electricity': 'Electricity',
            'water': 'Water'
        }
        
        try:
            current_user.balance -= total
            
            transaction = create_transaction(
                user_id=current_user.id,
                transaction_type='utility',
                amount=amount,
                reference=f"{service_names.get(service_type, service_type)} to {account_number}",
                admin_fee=fee,
                is_sender=True
            )
            
            db.session.add(transaction)
            db.session.commit()
            
            flash(f'Successfully paid {format_currency(amount)} for {service_names.get(service_type, service_type)}. Fee: {format_currency(fee)}', 'success')
            return redirect(url_for('user.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash('Payment failed. Please try again.', 'error')
    
    return render_template('utilities.html', form=form, format_currency=format_currency)

@user_bp.route('/goals', methods=['GET', 'POST'])
@login_required
def goals():
    """Financial goals management"""
    form = GoalForm()
    
    if form.validate_on_submit():
        try:
            deadline = form.deadline.data if form.deadline.data else None
            
            goal = FinancialGoal(
                user_id=current_user.id,
                goal_name=form.goal_name.data,
                target_amount=float(form.target_amount.data),
                deadline=deadline
            )
            
            db.session.add(goal)
            db.session.commit()
            flash('Goal created successfully!', 'success')
            return redirect(url_for('user.goals'))
        except Exception as e:
            db.session.rollback()
            flash('Failed to create goal. Please try again.', 'error')
    
    user_goals = FinancialGoal.query.filter_by(
        user_id=current_user.id
    ).order_by(
        FinancialGoal.created_at.desc()
    ).all()
    
    return render_template('goals.html', form=form, goals=user_goals, format_currency=format_currency)

@user_bp.route('/goal/<int:goal_id>/deposit', methods=['POST'])
@login_required
def goal_deposit(goal_id):
    """Deposit money into goal"""
    goal = FinancialGoal.query.get_or_404(goal_id)
    
    if goal.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('user.goals'))
    
    try:
        amount = float(request.form.get('amount', 0))
    except (ValueError, TypeError):
        flash('Invalid amount.', 'error')
        return redirect(url_for('user.goals'))
    
    if amount <= 0:
        flash('Invalid amount.', 'error')
        return redirect(url_for('user.goals'))
    
    if not current_user.can_afford(amount):
        flash('Insufficient balance.', 'error')
        return redirect(url_for('user.goals'))
    
    try:
        current_user.balance -= amount
        goal.add_amount(amount)
        
        transaction = create_transaction(
            user_id=current_user.id,
            transaction_type='goal_deposit',
            amount=amount,
            reference=goal.goal_name,
            is_sender=True
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        flash(f'Successfully deposited {format_currency(amount)} to {goal.goal_name}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Deposit failed. Please try again.', 'error')
    
    return redirect(url_for('user.goals'))

@user_bp.route('/goal/<int:goal_id>/withdraw', methods=['POST'])
@login_required
def goal_withdraw(goal_id):
    """Withdraw money from goal"""
    goal = FinancialGoal.query.get_or_404(goal_id)
    
    if goal.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('user.goals'))
    
    try:
        amount = float(request.form.get('amount', 0))
    except (ValueError, TypeError):
        flash('Invalid amount.', 'error')
        return redirect(url_for('user.goals'))
    
    if amount <= 0:
        flash('Invalid amount.', 'error')
        return redirect(url_for('user.goals'))
    
    if amount > goal.current_amount:
        flash('Insufficient balance in goal.', 'error')
        return redirect(url_for('user.goals'))
    
    try:
        goal.withdraw_amount(amount)
        current_user.balance += amount
        
        transaction = create_transaction(
            user_id=current_user.id,
            transaction_type='goal_withdrawal',
            amount=amount,
            reference=goal.goal_name,
            is_sender=True
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        flash(f'Successfully withdrew {format_currency(amount)} from {goal.goal_name}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Withdrawal failed. Please try again.', 'error')
    
    return redirect(url_for('user.goals'))

@user_bp.route('/history')
@login_required
def history():
    """Transaction history"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    transactions = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Transaction.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('history.html',
        transactions=transactions,
        format_currency=format_currency,
        format_datetime=format_datetime
    )

# FIXED: Route name matches template reference
@user_bp.route('/undo_transaction/<int:transaction_id>', methods=['POST'])
@login_required
def undo_transaction_route(transaction_id):
    """Undo a transaction"""
    success, message = undo_transaction(transaction_id, current_user.id)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    
    return redirect(url_for('user.history'))

@user_bp.route('/profile')
@login_required
def profile():
    """User profile"""
    # Get recent transactions for the profile page
    recent_transactions = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Transaction.created_at.desc()
    ).limit(3).all()
    
    return render_template('profile.html', 
        user=current_user, 
        recent_transactions=recent_transactions,
        format_currency=format_currency,
        format_datetime=format_datetime
    )