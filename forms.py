from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, DecimalField, DateField, SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, NumberRange, Optional
from models import User
import re
from datetime import datetime, date

class RegistrationForm(FlaskForm):
    full_name = StringField('Full Name', validators=[
        DataRequired(),
        Length(min=2, max=100, message='Name must be between 2 and 100 characters')
    ])
    
    email = StringField('Email', validators=[
        DataRequired(),
        Email(message='Please enter a valid email address'),
        Length(max=120)
    ])
    
    id_number = StringField('ID Number', validators=[
        DataRequired(),
        Length(min=13, max=13, message='South African ID must be 13 digits'),
    ])
    
    phone = StringField('Phone Number', validators=[
        DataRequired(),
        Length(min=10, max=10, message='Phone number must be 10 digits'),
    ])
    
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters'),
        EqualTo('confirm_password', message='Passwords must match')
    ])
    
    confirm_password = PasswordField('Confirm Password')
    submit = SubmitField('Register')
    
    def validate_id_number(self, field):
        if not field.data.isdigit():
            raise ValidationError('ID number must contain only digits')
        
        if User.query.filter_by(id_number=field.data).first():
            raise ValidationError('This ID number is already registered')
    
    def validate_phone(self, field):
        if not field.data.isdigit():
            raise ValidationError('Phone number must contain only digits')
        
        if not field.data.startswith('0'):
            raise ValidationError('Phone number must start with 0')
    
    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('This email is already registered')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired(),
        Email()
    ])
    
    password = PasswordField('Password', validators=[
        DataRequired()
    ])
    
    submit = SubmitField('Login')

class DepositForm(FlaskForm):
    amount = DecimalField('Amount', validators=[
        DataRequired(),
        NumberRange(min=10, max=50000, message='Amount must be between R10 and R50,000')
    ], places=2)
    
    submit = SubmitField('Deposit')

class TransferForm(FlaskForm):
    account_number = StringField('Account Number', validators=[
        DataRequired(),
        Length(min=10, max=10, message='Account number must be 10 digits')
    ])
    
    amount = DecimalField('Amount', validators=[
        DataRequired(),
        NumberRange(min=1, message='Amount must be at least R1')
    ], places=2)
    
    reference = StringField('Reference (Optional)', validators=[
        Length(max=100)
    ])
    
    submit = SubmitField('Transfer')
    
    def validate_account_number(self, field):
        if not field.data.isdigit():
            raise ValidationError('Account number must contain only digits')

class UtilityPaymentForm(FlaskForm):
    service_type = SelectField('Service', choices=[
        ('airtime', 'Airtime'),
        ('data', 'Mobile Data'),
        ('electricity', 'Electricity'),
        ('water', 'Water')
    ], validators=[DataRequired()])
    
    account_number = StringField('Account/Phone Number', validators=[
        DataRequired(),
        Length(min=1, max=20, message='Number must be between 1-20 characters')
    ])
    
    amount = DecimalField('Amount', validators=[
        DataRequired(),
        NumberRange(min=1, max=5000, message='Amount must be between R1 and R5,000')
    ], places=2)
    
    submit = SubmitField('Pay Now')
    
    def validate_account_number(self, field):
        service_type = self.service_type.data if hasattr(self, 'service_type') else ''
        
        if service_type in ['airtime', 'data']:
            if not field.data.isdigit():
                raise ValidationError('Phone number must contain only digits for airtime and data')
            if len(field.data) != 10:
                raise ValidationError('Phone number must be 10 digits for airtime and data')

class GoalForm(FlaskForm):
    goal_name = StringField('Goal Name', validators=[
        DataRequired(),
        Length(min=2, max=100)
    ])
    
    target_amount = DecimalField('Target Amount', validators=[
        DataRequired(),
        NumberRange(min=1, message='Amount must be at least R1')
    ], places=2)
    
    deadline = DateField('Deadline (Optional)', format='%Y-%m-%d', validators=[Optional()])
    submit = SubmitField('Create Goal')
    
    def validate_deadline(self, field):
        if field.data and field.data < date.today():
            raise ValidationError('Deadline cannot be in the past. Please choose a future date.')

class GoalTransactionForm(FlaskForm):
    amount = DecimalField('Amount', validators=[
        DataRequired(),
        NumberRange(min=1, message='Amount must be at least R1')
    ], places=2)
    
    submit = SubmitField('Process')

class AdminLoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class ContactForm(FlaskForm):
    full_name = StringField('Full Name', validators=[
        DataRequired(),
        Length(min=2, max=100, message='Name must be between 2 and 100 characters')
    ])
    
    email = StringField('Your Email Address', validators=[
        DataRequired(),
        Email(message='Please enter a valid email address'),
        Length(max=120)
    ])
    
    subject = StringField('Subject', validators=[
        DataRequired(),
        Length(min=5, max=200, message='Subject must be between 5 and 200 characters')
    ])
    
    message = TextAreaField('Your Message', validators=[
        DataRequired(),
        Length(min=10, max=2000, message='Message must be between 10 and 2000 characters')
    ])
    
    submit = SubmitField('Send Message')