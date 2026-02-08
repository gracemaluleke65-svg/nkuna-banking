from datetime import datetime, timedelta, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
import random

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """User model"""
    __tablename__ = 'nkb_users'
    
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    id_number = db.Column(db.String(13), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(10), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    account_number = db.Column(db.String(10), unique=True, nullable=False, index=True)
    balance = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships with cascade delete
    transactions = db.relationship('Transaction', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    goals = db.relationship('FinancialGoal', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    beneficiaries = db.relationship('Beneficiary', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    chat_messages = db.relationship('ChatMessage', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @staticmethod
    def generate_account_number():
        while True:
            account_number = str(random.randint(1000000000, 9999999999))
            if not User.query.filter_by(account_number=account_number).first():
                return account_number
    
    def can_afford(self, amount, include_fee=False, fee=0):
        total = amount + fee if include_fee else amount
        return self.balance >= total
    
    def __repr__(self):
        return f'<User {self.account_number}: {self.full_name}>'

class Transaction(db.Model):
    """Transaction model"""
    __tablename__ = 'nkb_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('nkb_users.id'), nullable=False, index=True)
    transaction_type = db.Column(db.String(20), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    reference = db.Column(db.String(100))
    recipient_account_number = db.Column(db.String(10))
    recipient_name = db.Column(db.String(100))
    sender_account_number = db.Column(db.String(10))
    sender_name = db.Column(db.String(100))
    is_sender = db.Column(db.Boolean, default=True)
    status = db.Column(db.String(20), default='completed', index=True)
    admin_fee = db.Column(db.Float, default=0.0)
    can_be_undone_until = db.Column(db.DateTime)
    original_transaction_id = db.Column(db.Integer, db.ForeignKey('nkb_transactions.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    reversal = db.relationship('Transaction', backref=db.backref('original', remote_side=[id]))
    
    def can_be_undone(self):
        if not self.can_be_undone_until:
            return False
        if not self.is_sender:
            return False
        return datetime.utcnow() < self.can_be_undone_until and self.status == 'completed'
    
    def calculate_undo_deadline(self):
        return datetime.utcnow() + timedelta(minutes=Config.UNDO_MINUTES)
    
    def get_description(self):
        descriptions = {
            'deposit': 'Deposit',
            'transfer': f'Transfer to {self.recipient_name or self.recipient_account_number}',
            'utility': f'Utility Payment: {self.reference}',
            'goal_deposit': f'Goal Deposit: {self.reference}',
            'goal_withdrawal': f'Goal Withdrawal: {self.reference}',
            'reversal': f'Reversal of transaction #{self.original_transaction_id}'
        }
        return descriptions.get(self.transaction_type, self.transaction_type)
    
    def is_incoming(self):
        if self.transaction_type in ['deposit', 'goal_withdrawal', 'reversal']:
            return True
        elif self.transaction_type == 'transfer':
            return not self.is_sender
        return False
    
    def get_amount_display(self):
        if self.is_incoming():
            return f"+{self.amount:,.2f}"
        else:
            return f"-{self.amount:,.2f}"
    
    def get_amount_class(self):
        if self.is_incoming():
            return "text-success"
        else:
            return "text-danger"
    
    def __repr__(self):
        return f'<Transaction {self.id}: {self.transaction_type} R{self.amount}>'

class FinancialGoal(db.Model):
    """Financial goal model"""
    __tablename__ = 'nkb_financial_goals'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('nkb_users.id'), nullable=False, index=True)
    goal_name = db.Column(db.String(100), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0.0)
    deadline = db.Column(db.Date)
    is_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def progress_percentage(self):
        if self.target_amount == 0:
            return 0
        return min(100, (self.current_amount / self.target_amount) * 100)
    
    def add_amount(self, amount):
        self.current_amount += amount
        if self.current_amount >= self.target_amount:
            self.is_completed = True
            self.current_amount = self.target_amount
    
    def withdraw_amount(self, amount):
        if amount <= self.current_amount:
            self.current_amount -= amount
            if self.current_amount < self.target_amount:
                self.is_completed = False
            return True
        return False
    
    def __repr__(self):
        return f'<Goal {self.goal_name}: R{self.current_amount}/R{self.target_amount}>'

class Beneficiary(db.Model):
    """Beneficiary model for quick transfers"""
    __tablename__ = 'nkb_beneficiaries'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('nkb_users.id'), nullable=False, index=True)
    account_number = db.Column(db.String(10), nullable=False)
    nickname = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'account_number', name='nkb_unique_beneficiary'),)
    
    def __repr__(self):
        return f'<Beneficiary {self.nickname or self.account_number}>'

class AdminFeeConfig(db.Model):
    """Admin fee configuration model"""
    __tablename__ = 'nkb_admin_fees_config'
    
    id = db.Column(db.Integer, primary_key=True)
    fee_name = db.Column(db.String(50), nullable=False)
    fee_percentage = db.Column(db.Float, default=0.0)
    minimum_fee = db.Column(db.Float, default=0.0)
    maximum_fee = db.Column(db.Float)
    applies_to_transaction_type = db.Column(db.String(20), index=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def calculate_fee(self, amount):
        if not self.is_active:
            return 0.0
        
        fee = (self.fee_percentage / 100) * amount
        
        if self.minimum_fee and fee < self.minimum_fee:
            fee = self.minimum_fee
        
        if self.maximum_fee and fee > self.maximum_fee:
            fee = self.maximum_fee
        
        return round(fee, 2)
    
    @staticmethod
    def get_transfer_fee(amount):
        fee_config = AdminFeeConfig.query.filter_by(
            applies_to_transaction_type='transfer',
            is_active=True
        ).first()
        
        if fee_config:
            return fee_config.calculate_fee(amount)
        
        fee = (Config.TRANSFER_FEE_PERCENT / 100) * amount
        fee = max(Config.MIN_TRANSFER_FEE, min(fee, Config.MAX_TRANSFER_FEE))
        return round(fee, 2)
    
    @staticmethod
    def get_utility_fee():
        fee_config = AdminFeeConfig.query.filter_by(
            applies_to_transaction_type='utility',
            is_active=True
        ).first()
        
        if fee_config:
            return fee_config.calculate_fee(0)
        
        return Config.UTILITY_FEE_FIXED
    
    def __repr__(self):
        return f'<FeeConfig {self.fee_name}: {self.fee_percentage}%>'

class ChatMessage(db.Model):
    """Chat message model for admin support"""
    __tablename__ = 'nkb_chat_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('nkb_users.id'), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        sender = "Admin" if self.is_admin else "User"
        return f'<ChatMessage {self.id}: {sender} - {self.message[:30]}...>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'message': self.message,
            'is_admin': self.is_admin,
            'is_read': self.is_read,
            'created_at': self.created_at.strftime('%d %b %Y, %I:%M %p'),
            'sender_name': 'Admin' if self.is_admin else self.user.full_name
        }