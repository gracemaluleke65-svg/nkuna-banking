from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from flask_socketio import emit, join_room, leave_room
from models import db, ChatMessage, User
from utils import format_currency, format_datetime
from datetime import datetime

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

# Store active chat rooms (user_id -> room_id mapping)
active_chats = {}

@chat_bp.route('/')
@login_required
def chat():
    """User chat interface"""
    if current_user.is_admin:
        return render_template('chat/admin_chat.html', 
                             format_currency=format_currency,
                             format_datetime=format_datetime)
    return render_template('chat/user_chat.html',
                         format_currency=format_currency,
                         format_datetime=format_datetime)

@chat_bp.route('/history')
@login_required
def get_chat_history():
    """Get chat history for current user"""
    if current_user.is_admin:
        # Admin gets all recent messages grouped by user
        messages = ChatMessage.query.order_by(ChatMessage.created_at.desc()).limit(100).all()
        # Group by user
        user_chats = {}
        for msg in messages:
            uid = msg.user_id
            if uid not in user_chats:
                user_chats[uid] = []
            user_chats[uid].append(msg.to_dict())
        return jsonify({'success': True, 'chats': user_chats})
    else:
        # User gets only their messages
        messages = ChatMessage.query.filter_by(user_id=current_user.id).order_by(ChatMessage.created_at.asc()).all()
        return jsonify({'success': True, 'messages': [msg.to_dict() for msg in messages]})

@chat_bp.route('/users')
@login_required
def get_chat_users():
    """Get list of users with active chats (admin only)"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    # Get users who have sent messages
    subquery = db.session.query(ChatMessage.user_id).distinct().subquery()
    users = User.query.filter(User.id.in_(subquery)).all()
    
    user_list = []
    for user in users:
        unread_count = ChatMessage.query.filter_by(user_id=user.id, is_admin=False, is_read=False).count()
        last_message = ChatMessage.query.filter_by(user_id=user.id).order_by(ChatMessage.created_at.desc()).first()
        
        user_list.append({
            'id': user.id,
            'full_name': user.full_name,
            'email': user.email,
            'account_number': user.account_number,
            'unread_count': unread_count,
            'last_message': last_message.to_dict() if last_message else None
        })
    
    # Sort by unread count (descending) then by last message time
    user_list.sort(key=lambda x: (x['unread_count'], x['last_message']['created_at'] if x['last_message'] else ''), reverse=True)
    
    return jsonify({'success': True, 'users': user_list})

@chat_bp.route('/mark_read/<int:user_id>', methods=['POST'])
@login_required
def mark_messages_read(user_id):
    """Mark all messages from a user as read (admin only)"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    ChatMessage.query.filter_by(user_id=user_id, is_admin=False, is_read=False).update({'is_read': True})
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Messages marked as read'})

# SocketIO event handlers
def register_socketio_handlers(socketio):
    @socketio.on('connect')
    def handle_connect():
        if not current_user.is_authenticated:
            return False
        
        room = f"user_{current_user.id}"
        join_room(room)
        
        if current_user.is_admin:
            join_room('admin_room')
            emit('connected', {'message': 'Connected as admin', 'room': 'admin_room'})
        else:
            active_chats[current_user.id] = room
            emit('connected', {'message': 'Connected to support', 'room': room})
            
            # Notify admins that a user is online
            emit('user_online', {
                'user_id': current_user.id,
                'full_name': current_user.full_name,
                'email': current_user.email
            }, broadcast=True, namespace='/', room='admin_room')

    @socketio.on('disconnect')
    def handle_disconnect():
        if current_user.is_authenticated and not current_user.is_admin:
            if current_user.id in active_chats:
                del active_chats[current_user.id]
            
            # Notify admins that user is offline
            emit('user_offline', {
                'user_id': current_user.id
            }, broadcast=True, namespace='/', room='admin_room')

    @socketio.on('send_message')
    def handle_message(data):
        if not current_user.is_authenticated:
            return
        
        message_text = data.get('message', '').strip()
        recipient_id = data.get('recipient_id')
        
        if not message_text:
            return
        
        # Create message record
        is_admin = current_user.is_admin
        
        if is_admin:
            # Admin sending to specific user
            if not recipient_id:
                emit('error', {'message': 'Recipient ID required'})
                return
            user_id = recipient_id
            room = f"user_{recipient_id}"
        else:
            # User sending to admin
            user_id = current_user.id
            room = f"user_{current_user.id}"
        
        chat_msg = ChatMessage(
            user_id=user_id,
            message=message_text,
            is_admin=is_admin,
            is_read=False
        )
        
        try:
            db.session.add(chat_msg)
            db.session.commit()
            
            message_data = chat_msg.to_dict()
            
            # Send to recipient
            emit('new_message', message_data, room=room)
            
            # If admin sent, also confirm to admin room
            if is_admin:
                emit('message_sent', message_data, room='admin_room')
            else:
                # Notify admins of new message
                emit('new_user_message', {
                    'user_id': current_user.id,
                    'full_name': current_user.full_name,
                    'message': message_data
                }, room='admin_room')
                
        except Exception as e:
            db.session.rollback()
            emit('error', {'message': 'Failed to send message'})

    @socketio.on('typing')
    def handle_typing(data):
        """Handle typing indicators"""
        if not current_user.is_authenticated:
            return
        
        is_typing = data.get('typing', False)
        recipient_id = data.get('recipient_id')
        
        if current_user.is_admin and recipient_id:
            room = f"user_{recipient_id}"
            emit('admin_typing', {'typing': is_typing}, room=room)
        elif not current_user.is_admin:
            emit('user_typing', {
                'user_id': current_user.id,
                'full_name': current_user.full_name,
                'typing': is_typing
            }, room='admin_room')