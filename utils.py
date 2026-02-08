import random
import string
from datetime import datetime, timedelta
from models import db, User, Transaction, AdminFeeConfig
from config import Config

def generate_account_number():
    """Generate a unique 10-digit account number"""
    while True:
        account_number = ''.join(random.choices(string.digits, k=10))
        if not User.query.filter_by(account_number=account_number).first():
            return account_number

def format_currency(amount):
    """Format amount as South African Rand"""
    return f"R{amount:,.2f}"

def format_datetime(dt, include_time=True):
    """Format datetime for display"""
    if not dt:
        return ""
    
    if include_time:
        return dt.strftime("%d %b %Y, %I:%M %p")
    return dt.strftime("%d %b %Y")

def calculate_transfer_fee(amount):
    """Calculate transfer fee for given amount"""
    return AdminFeeConfig.get_transfer_fee(amount)

def calculate_utility_fee():
    """Get utility fee"""
    return AdminFeeConfig.get_utility_fee()

def verify_account(account_number):
    """Verify if account exists and is active"""
    if not account_number or len(account_number) != 10 or not account_number.isdigit():
        return None
    
    user = User.query.filter_by(
        account_number=account_number,
        is_active=True
    ).first()
    
    if user:
        return {
            'account_number': user.account_number,
            'full_name': user.full_name,
            'verified': True
        }
    
    return None

def create_transaction(user_id, transaction_type, amount, **kwargs):
    """Create a transaction record"""
    transaction = Transaction(
        user_id=user_id,
        transaction_type=transaction_type,
        amount=amount,
        reference=kwargs.get('reference', ''),
        recipient_account_number=kwargs.get('recipient_account_number'),
        recipient_name=kwargs.get('recipient_name'),
        sender_account_number=kwargs.get('sender_account_number'),
        sender_name=kwargs.get('sender_name'),
        is_sender=kwargs.get('is_sender', True),  # Default to True (user initiated)
        admin_fee=kwargs.get('admin_fee', 0.0)
    )
    
    if transaction_type in ['deposit', 'transfer', 'utility']:
        transaction.can_be_undone_until = datetime.now() + timedelta(minutes=Config.UNDO_MINUTES)
    
    return transaction

def undo_transaction(transaction_id, user_id):
    """Undo a transaction if within 15 minutes"""
    transaction = Transaction.query.get(transaction_id)
    
    if not transaction:
        return False, "Transaction not found"
    
    if transaction.user_id != user_id:
        return False, "You don't have permission to undo this transaction"
    
    if not transaction.can_be_undone():
        return False, "This transaction can no longer be undone (15-minute window expired) or you cannot undo received transfers"
    
    if transaction.status == 'reversed':
        return False, "This transaction has already been reversed"
    
    user = User.query.get(user_id)
    
    if transaction.transaction_type == 'deposit':
        if user.balance < transaction.amount:
            return False, "Insufficient balance to reverse deposit"
        user.balance -= transaction.amount
    
    elif transaction.transaction_type in ['transfer', 'utility']:
        user.balance += transaction.amount
    
    reversal = Transaction(
        user_id=user_id,
        transaction_type='reversal',
        amount=transaction.amount,
        reference=f"Reversal of {transaction.transaction_type}",
        status='completed',
        original_transaction_id=transaction.id,
        is_sender=True
    )
    
    transaction.status = 'reversed'
    
    db.session.add(reversal)
    db.session.commit()
    
    return True, "Transaction successfully reversed"

def seed_default_fees():
    """Seed default fee configuration if not exists"""
    if AdminFeeConfig.query.count() == 0:
        fees = [
            AdminFeeConfig(
                fee_name="Transfer Fee",
                fee_percentage=1.0,
                minimum_fee=5.0,
                maximum_fee=50.0,
                applies_to_transaction_type="transfer",
                is_active=True
            ),
            AdminFeeConfig(
                fee_name="Utility Payment Fee",
                fee_percentage=0.0,
                minimum_fee=5.0,
                maximum_fee=5.0,
                applies_to_transaction_type="utility",
                is_active=True
            )
        ]
        
        db.session.add_all(fees)
        db.session.commit()
        print("Default fee configuration seeded")

def get_system_stats():
    """Get system statistics for admin dashboard"""
    total_users = User.query.count()
    total_balance = db.session.query(db.func.sum(User.balance)).scalar() or 0
    total_transactions = Transaction.query.count()
    total_fees = db.session.query(db.func.sum(Transaction.admin_fee)).scalar() or 0
    
    recent_transactions = Transaction.query.order_by(
        Transaction.created_at.desc()
    ).limit(10).all()
    
    return {
        'total_users': total_users,
        'total_balance': total_balance,
        'total_transactions': total_transactions,
        'total_fees': total_fees,
        'recent_transactions': recent_transactions
    }