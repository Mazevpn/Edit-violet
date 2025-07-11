import logging
from telethon import events, Button
from datetime import datetime
from models.user import User
import json
import os

logger = logging.getLogger(__name__)

# Dictionary to store user states
user_states = {}

# Dictionary to store chat messages in memory
# Format: {user_id: [{'message': 'text', 'is_from_admin': False, 'admin_id': None, 'timestamp': datetime, 'is_read': False, 'media_type': None, 'media_id': None}]}
chat_messages = {}

def save_chats_to_file():
    """Save chat messages to a JSON file"""
    # Convert datetime objects to strings
    serializable_chats = {}
    for user_id, messages in chat_messages.items():
        serializable_chats[str(user_id)] = []
        for msg in messages:
            serializable_msg = msg.copy()
            serializable_msg['timestamp'] = serializable_msg['timestamp'].isoformat()
            serializable_chats[str(user_id)].append(serializable_msg)
    
    with open('chat_messages.json', 'w') as f:
        json.dump(serializable_chats, f)

def load_chats_from_file():
    """Load chat messages from a JSON file"""
    if not os.path.exists('chat_messages.json'):
        return {}
    
    with open('chat_messages.json', 'r') as f:
        serializable_chats = json.load(f)
    
    # Convert string timestamps back to datetime objects
    result = {}
    for user_id_str, messages in serializable_chats.items():
        user_id = int(user_id_str)
        result[user_id] = []
        for msg in messages:
            msg['timestamp'] = datetime.fromisoformat(msg['timestamp'])
            result[user_id].append(msg)
    
    return result

async def handle_member_chat_callback(event, client):
    """
    Handle member chat functionality for callback queries
    """
    user_id = event.sender_id
    
    # Check if the button was clicked
    if event.data == b'kirim_pesan_admin':
        await start_chat_with_admin(event, client, user_id)
        return
    
    # Check if the exit chat button was clicked
    if event.data == b'exit_chat':
        await exit_chat_mode(event, user_id)
        return

async def handle_member_chat_message(event, client):
    """
    Handle member chat functionality for regular messages
    """
    user_id = event.sender_id
    
    # Check if this is a /start command
    if hasattr(event, 'message') and event.message.text == '/start':
        # Exit chat mode and show main menu
        if user_id in user_states and user_states[user_id].get('chat_mode'):
            await exit_chat_mode(event, user_id)
            return True  # Signal that we handled the /start command
    
    # Check if user is in chat mode
    if user_id in user_states and user_states[user_id].get('chat_mode'):
        await forward_message_to_admins(event, client, user_id)
        return True  # Signal that we handled the message
    
    return False  # Signal that we did not handle the message

async def exit_chat_mode(event, user_id):
    """Exit chat mode and return to main menu"""
    # Clear user state
    if user_id in user_states:
        del user_states[user_id]
    
    try:
        # Import di dalam fungsi untuk menghindari circular import
        from handlers.member_menu import member_start_menu
        
        # Check if this is a callback query or a message
        if hasattr(event, 'edit'):
            # This is a callback query
            await event.edit(
                "🏠 **Menu Utama**\n\n"
                "Silakan pilih layanan yang Anda butuhkan:",
                buttons=member_start_menu()
            )
        else:
            # This is a message
            await event.respond(
                "🏠 **Menu Utama**\n\n"
                "Silakan pilih layanan yang Anda butuhkan:",
                buttons=member_start_menu()
            )
    except ImportError as e:
        logger.error(f"Error importing member_menu: {e}")
        # Fallback jika modul tidak ditemukan
        fallback_message = (
            "🏠 **Menu Utama**\n\n"
            "Anda telah keluar dari mode chat.\n"
            "Silakan ketik /start untuk melihat menu utama."
        )
        
        if hasattr(event, 'edit'):
            await event.edit(fallback_message)
        else:
            await event.respond(fallback_message)

async def start_chat_with_admin(event, client, user_id):
    """
    Start chat with admin process
    """
    # Set user state to chat mode
    user_states[user_id] = {'chat_mode': True}
    
    # Send instructions to user
    await event.edit(
        "📲 **Kirim Pesan ke Admin**\n\n"
        "Silakan ketik pesan yang ingin Anda sampaikan kepada admin.\n"
        "Anda juga dapat mengirim foto, video, atau dokumen.\n"
        "Admin akan merespons secepatnya.\n\n"
        "Untuk keluar dari mode chat, klik tombol di bawah atau ketik /start.",
        buttons=[[Button.inline("❌ Keluar dari Chat", b'exit_chat')]]
    )

async def forward_message_to_admins(event, client, user_id):
    """
    Forward message from member to all admins
    """
    # Get user information
    user = User.get_by_id(user_id)
    if not user:
        user = User.create_or_update(
            user_id=user_id,
            username=event.sender.username,
            first_name=event.sender.first_name
        )
    
    # Get all admins
    admins = User.get_all_admins()
    
    if not admins:
        await event.respond("❌ Tidak ada admin yang tersedia saat ini. Silakan coba lagi nanti.")
        return
    
    # Create message to forward
    sender_info = f"👤 **Pesan dari Member**\n"
    sender_info += f"ID: `{user_id}`\n"
    sender_info += f"Nama: {user.first_name or 'Tidak diketahui'}\n"
    sender_info += f"Username: @{user.username or 'Tidak diketahui'}\n"
    sender_info += f"Waktu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    # Initialize message data
    message_content = ""
    media_type = None
    media_id = None
    
    # Check message type and content
    if hasattr(event, 'message'):
        message = event.message
        
        # Check if message has media
        if message.media:
            if message.photo:
                media_type = "photo"
                sender_info += "📷 **Foto:**"
                if message.text:
                    sender_info += f"\n{message.text}"
                    message_content = message.text
            elif message.document:
                media_type = "document"
                sender_info += f"📎 **Dokumen:** {message.document.attributes[0].file_name if hasattr(message.document.attributes[0], 'file_name') else 'File'}"
                if message.text:
                    sender_info += f"\n{message.text}"
                    message_content = message.text
            elif message.video:
                media_type = "video"
                sender_info += "🎥 **Video:**"
                if message.text:
                    sender_info += f"\n{message.text}"
                    message_content = message.text
            elif message.voice:
                media_type = "voice"
                sender_info += "🎤 **Pesan Suara:**"
                if message.text:
                    sender_info += f"\n{message.text}"
                    message_content = message.text
            else:
                media_type = "other"
                sender_info += "📤 **Media:**"
                if message.text:
                    sender_info += f"\n{message.text}"
                    message_content = message.text
        else:
            # Text message
            message_content = message.text
            sender_info += f"📝 **Pesan:**\n{message_content}"
    
    # Save message to memory
    if user_id not in chat_messages:
        chat_messages[user_id] = []
    
    chat_messages[user_id].append({
        'message': message_content,
        'is_from_admin': False,
        'admin_id': None,
        'timestamp': datetime.now(),
        'is_read': False,
        'media_type': media_type,
        'media_id': media_id
    })
    
    # Forward to all admins
    for admin in admins:
        try:
            # First send info message
            admin_msg = await client.send_message(
                admin.user_id,
                sender_info,
                buttons=[[Button.inline(f"💬 Balas ke {user.first_name or 'Member'}", f"reply_{user_id}".encode())]]
            )
            
            # Then forward the actual media if exists
            if media_type:
                await event.message.forward_to(admin.user_id)
        except Exception as e:
            logger.error(f"Failed to send message to admin {admin.user_id}: {e}")
    
    # Confirm to user
    await event.respond(
        "✅ Pesan Anda telah dikirim ke admin.\n"
        "Mohon tunggu balasan dari admin.\n\n"
        "Anda dapat mengirim pesan lain atau keluar dari mode chat.",
        buttons=[[Button.inline("❌ Keluar dari Chat", b'exit_chat')]]
    )

# Register handlers
async def register_handlers(client):
    """
    Register all handlers for member chat
    """
    @client.on(events.CallbackQuery(pattern=b'kirim_pesan_admin'))
    async def on_chat_button(event):
        await handle_member_chat_callback(event, client)
    
    @client.on(events.CallbackQuery(pattern=b'exit_chat'))
    async def on_exit_chat(event):
        await handle_member_chat_callback(event, client)
    
    @client.on(events.NewMessage())
    async def on_new_message(event):
        # Only process messages from private chats (not groups/channels)
        if event.is_private:
            user_id = event.sender_id
            
            # Handle chat messages first
            handled = await handle_member_chat_message(event, client)
            
            # If message was handled by chat handler, don't process further
            if handled:
                return
    
    logger.info("Member chat handlers registered successfully")
    return True
