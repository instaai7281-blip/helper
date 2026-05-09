# ---------------------------------------------------
# File Name: get_func.py
# Description: A Pyrogram bot for downloading files from Telegram channels or groups 
#              and uploading them back to Telegram.
# Author: Gagan
# GitHub: https://github.com/devgaganin/
# Telegram: https://t.me/team_spy_pro
# YouTube: https://youtube.com/@dev_gagan
# Created: 2025-01-11
# Last Modified: 2025-02-01
# Version: 2.0.5
# License: MIT License
# Improved logic handles
# ---------------------------------------------------

import asyncio
import time
import gc
import os
import re
from typing import Callable
from devgagan import app, get_client
import aiofiles
from devgagan import sex as gf
from telethon.tl.types import DocumentAttributeVideo, Message
from telethon.sessions import StringSession
import pymongo
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import ChannelBanned, ChannelInvalid, ChannelPrivate, ChatIdInvalid, ChatInvalid
from pyrogram.enums import MessageMediaType, ParseMode
from devgagan.core.func import *
from pyrogram.errors import RPCError
from pyrogram.types import Message
from config import MONGO_DB as MONGODB_CONNECTION_STRING, LOG_GROUP, OWNER_ID, STRING, STRINGS, API_ID, API_HASH, THUMBNAIL_DIR
from devgagan.core.mongo import db as odb
from telethon import TelegramClient, events, Button
from devgagantools import fast_upload, fast_download
from datetime import datetime
import asyncio
import unicodedata
from datetime import datetime
from pyrogram.enums import ParseMode
from telethon.tl.types import DocumentAttributeVideo
import random
import io
try:
    from PyPDF2 import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
except ImportError:
    PdfReader = PdfWriter = canvas = None

# Define custom emojis for random selection
CUSTOM_EMOJIS = ["🍁", "🍀", "👑", "✨", "🦋", "🌟", "💖"]

# Clean filename helper
def clean_text_advanced(text, user_tag, delete_words=None, replacements=None):
    if not text:
        return text
    
    # List of unwanted phrases (case-insensitive)
    unwanted_phrases = [
        r'team[\s_\-\.]*jnc',
        r'team[\s_\-\.]*spy',
        r'team[\s_\-\.]*spay',
        r'team[\s_\-\.]*spy[\s_\-\.]*pro',
        r'let\'?s\s*help',
        r'✧\s*𝚃𝙷𝙴\s*𝚂𝚃𝚄𝙳𝚈\s*𝚅𝙰𝚄𝙻𝚃\s*✧\s*🏝️?',
        r'devgagan',
        r'@Src_pro_bot',
        r'Chosen\s*One',
        r'jnc',
        r'spy',
        r'spay',
        r'lets\s*help'
    ]
    
    for phrase in unwanted_phrases:
        text = re.sub(f'(?i)[*_]*{phrase}[*_]*', '', text)
    
    # Replace any @mention with the specific user tag
    text = re.sub(r'@\w+', user_tag, text)

    # Replace brackets with stylized ones
    text = re.sub(r'[({[]', '〘', text)
    text = re.sub(r'[)}\]]', '〙', text)

    # Rebrand common extraction markers
    text = re.sub(r'(?i)(Extracted|Downloaded|Uploaded)[\s_]*By\s*[:➤>–\-]*\s*[^\n]*', r'<b>Sᴛꪮʟᴇɴ Hᴀᴘᴘɪɴᴇss</b>', text)

    # Apply custom delete words
    if delete_words:
        for word in delete_words:
            text = text.replace(word, ' ')

    # Apply custom replacements
    if replacements:
        for old, new in replacements.items():
            text = text.replace(old, new)
    
    # Remove extra horizontal spaces but PRESERVE newlines
    text = re.sub(r'[ \t]+', ' ', text).strip()
    return text


def clean_filename(text, user_tag):
    if not text:
        return "file"
    
    # Remove unwanted branding first
    text = clean_text_advanced(text, user_tag, None, None)

    # Normalize to separate combined accents
    text = unicodedata.normalize("NFKC", text)

    # Remove emojis and unwanted symbols (but keep letters from all scripts)
    text = ''.join(
        char for char in text
        if not unicodedata.category(char).startswith('S')  # Symbols (includes emojis)
        and not unicodedata.category(char).startswith('C')  # Other (control chars, etc.)
        and not unicodedata.category(char).startswith('P')  # Punctuation
        or char in ['.', '-', '_', '〘', '〙', '⛥']  # keep basic filename-safe symbols and user custom ones
    )

    # Normalize spaces, dashes, underscores
    text = re.sub(r'[_\s\-]+', ' ', text)

    # Add star to PDF files if requested
    if text.lower().endswith(".pdf"):
        # Replace .pdf at the end with ' ⛥.pdf'
        text = re.sub(r'(?i)\.pdf$', ' ⛥.pdf', text)

    # Final strip
    return text.strip()



# MongoDB database name and collection name
DB_NAME = "smart_users"
COLLECTION_NAME = "super_user"

VIDEO_EXTENSIONS = ['mp4', 'mov', 'avi', 'mkv', 'flv', 'wmv', 'webm', 'mpg', 'mpeg', '3gp', 'ts', 'm4v', 'f4v', 'vob']
DOCUMENT_EXTENSIONS = ['pdf', 'docs']

mongo_app = pymongo.MongoClient(MONGODB_CONNECTION_STRING)
db = mongo_app[DB_NAME]
collection = db[COLLECTION_NAME]

if STRINGS:
    from devgagan import pro
else:
    pro = None

user_progress = {}

async def is_enabled(user_id, media_type):
    data = await odb.get_data(user_id)
    if not data:
        return True
    filters = data.get("filters", {})
    return filters.get(media_type, True)

async def fetch_upload_method(user_id):
    """Fetch the user's preferred upload method."""
    user_data = collection.find_one({"user_id": user_id})
    return user_data.get("upload_method", "Pyrogram") if user_data else "Pyrogram"


async def add_pdf_watermark(input_path, watermark_text, grid=False, opacity=0.12):
    if not PdfReader:
        return input_path
    
    output_path = input_path.replace(".pdf", "_watermarked.pdf")
    try:
        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page in reader.pages:
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)

            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=(width, height))
            
            if grid:
                # --- Grid Watermark (Full Page) ---
                can.setFont("Helvetica-Bold", 18)
                can.setStrokeColorRGB(0.7, 0.7, 0.7)
                can.setFillAlpha(opacity / 1.5)
                for x in range(0, int(width), 150):
                    for y in range(0, int(height), 150):
                        can.saveState()
                        can.translate(x, y)
                        can.rotate(30)
                        can.drawCentredString(0, 0, watermark_text)
                        can.restoreState()
            else:
                # --- 1. Large Central Diagonal Watermark ---
                font_size = width / 10
                can.setFont("Helvetica-Bold", font_size)
                can.setStrokeColorRGB(0.6, 0.7, 0.8) # Subtle blue-grey
                can.setFillAlpha(opacity)
                
                can.saveState()
                can.translate(width / 2, height / 2)
                can.rotate(45)
                can.drawCentredString(0, 0, watermark_text)
                can.restoreState()

            # --- 2. Professional Footer Stamp ---
            can.setFont("Helvetica-BoldOblique", 10)
            can.setFillAlpha(0.5)
            can.setStrokeColorRGB(0.3, 0.3, 0.3)
            # Bottom Left
            can.drawString(20, 15, f"Original Content: {watermark_text}")
            # Bottom Right (Page info placeholder or branding)
            can.drawRightString(width - 20, 15, "Verified Secure PDF 🔒")
            
            # --- 3. Top Banner ---
            can.setFont("Helvetica", 8)
            can.setFillAlpha(0.3)
            can.drawCentredString(width / 2, height - 20, f"--- Exclusive Access for {watermark_text} members ---")

            can.save()
            packet.seek(0)
            
            watermark_pdf = PdfReader(packet)
            watermark_page = watermark_pdf.pages[0]
            
            page.merge_page(watermark_page)
            writer.add_page(page)

        with open(output_path, "wb") as f:
            writer.write(f)
        
        return output_path
    except Exception as e:
        print(f"Error adding powerful watermark: {e}")
        return input_path


def format_caption_to_html(caption: str) -> str:
    if not caption:
        return ""

    # Support standard Markdown to HTML conversion
    caption = re.sub(r"```(.*?)```", r"<pre>\1</pre>", caption, flags=re.DOTALL)
    caption = re.sub(r"`(.*?)`", r"<code>\1</code>", caption)
    caption = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", caption)
    caption = re.sub(r"\*(.*?)\*", r"<b>\1</b>", caption)
    caption = re.sub(r"__(.*?)__", r"<i>\1</i>", caption)
    caption = re.sub(r"_(.*?)_", r"<i>\1</i>", caption)
    caption = re.sub(r"~~(.*?)~~", r"<s>\1</s>", caption)
    caption = re.sub(r"\|\|(.*?)\|\|", r"<details>\1</details>", caption)
    caption = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2">\1</a>', caption)
    
    # Improved Blockquote support (trigger on any line starting with >)
    lines = caption.split("\n")
    new_lines = []
    in_quote = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(">"):
            if not in_quote:
                new_lines.append("<blockquote>")
                in_quote = True
            new_lines.append(stripped[1:].strip())
        else:
            if in_quote:
                new_lines.append("</blockquote>")
                in_quote = False
            new_lines.append(line)
    if in_quote:
        new_lines.append("</blockquote>")
    caption = "\n".join(new_lines)

    return caption.strip()

    

from pyrogram.enums import ParseMode
from datetime import datetime
from telethon.tl.types import DocumentAttributeVideo
import os, gc, time, asyncio
import shutil, subprocess, os, math

# Unified log_upload
async def log_upload(user_id, file_type, file_msg, upload_method, duration=None, file_name=None):
    try:
        user = await app.get_users(user_id)
        bot = await app.get_me()

        # Keep mention format exactly like you want
        user_mention = user.mention if user else "User"

        bot_name = f"{bot.first_name} (@{bot.username})" if bot else "Unknown Bot"
        display_text = file_msg.caption or file_name or "No caption/filename"
        clean_text = (display_text[:1000] + '...') if len(display_text) > 1000 else display_text

        text = (
            f"{clean_text}\n\n"
            f"📁 **log info:**\n"
            f"👤 **User:** {user_mention}\n"
            f"🆔 **User ID:** `{user_id}`\n"
        )

        text += f"🤖 **Saved by:** {bot_name}"

        await file_msg.copy(LOG_GROUP, caption=text)

    except Exception as e:
        await app.send_message(LOG_GROUP, f"❌ Log Error: `{e}`")


# Upload handler
async def upload_media(sender, target_chat_id, file, caption, edit, topic_id):
    try:
        upload_method = await fetch_upload_method(sender)
        metadata = video_metadata(file)

        # Extract metadata safely (only if video)
        width = metadata.get('width', 0)
        height = metadata.get('height', 0)
        duration = metadata.get('duration', 0)

        # ✅ Check for custom thumbnail first (for all media types)
        thumb_path = thumbnail(sender)

        # ✅ Fallback to auto-screenshot ONLY if it's a video and NO custom thumb exists
        # REPLACE THIS in devgagan/core/get_func.py (Line 175-179)

        if not thumb_path and file.lower().endswith(tuple(VIDEO_EXTENSIONS)):
            try:
                print(f"[DEBUG] Trying to create thumbnail for: {file}, duration: {duration}")
                thumb_path = await screenshot(file, duration, sender)
                if not thumb_path:
                    print(f"[ERROR] Screenshot returned None for user {sender}")
                else:
                    print(f"[SUCCESS] Thumbnail created: {thumb_path}")
            except Exception as e:
                print(f"[ERROR] Screenshot exception for {sender}: {str(e)}")
                import traceback
                traceback.print_exc()
                thumb_path = None

        ext = file.split('.')[-1].lower()
        raw_name = os.path.basename(file)
        
        # Get active tag for filename cleaning
        user_data = await odb.get_data(sender)
        active_tag = user_data.get("active_tag", "@Chosen_Onex_bot") if user_data else "@Chosen_Onex_bot"
        
        clean_name = clean_filename(os.path.splitext(raw_name)[0], active_tag)
        file_name = f"{clean_name}.{ext}"

        video_formats = set(VIDEO_EXTENSIONS)
        image_formats = {'jpg', 'png', 'jpeg'}

        # ✅ Caption is already formatted for user post by get_final_caption

        # ✅ Generate log caption separately
        user = await app.get_users(sender)
        bot = await app.get_me()
        user_mention = user.mention if user else "User"
        bot_name = f"{bot.first_name} (@{bot.username})" if bot else "Bot"

        display_text = caption or file_name or "No caption/filename"
        clean_text = (display_text[:1000] + '...') if len(display_text) > 1000 else display_text

        log_caption = (            
            f"📁 **log info:**\n"
            f"👤 **User:** {user_mention}\n"
            f"🆔 **User ID:** `{sender}`\n"
            f"🤖 **Saved by:** {bot_name}"
        )

        # ────── Pyrogram Upload ──────
        if upload_method == "Pyrogram":
            if ext in video_formats:
                # Send to user
                dm = await app.send_video(
                    chat_id=target_chat_id,
                    video=file,
                    caption=caption,
                    height=height,
                    width=width,
                    duration=duration,
                    thumb=thumb_path,
                    reply_to_message_id=topic_id,
                    parse_mode=ParseMode.HTML,
                    progress=progress_bar,
                    progress_args=("╔══━⚡️Uploading...⚡️━══╗\n", edit, time.time())
                )

            elif ext in image_formats:
                dm = await app.send_photo(
                    chat_id=target_chat_id,
                    photo=file,
                    caption=None,
                    progress=progress_bar,
                    reply_to_message_id=topic_id,
                    progress_args=("╔══━⚡️Uploading...⚡️━══╗\n", edit, time.time())
                )

            else:
                dm = await app.send_document(
                    chat_id=target_chat_id,
                    document=file,
                    caption=caption,
                    thumb=thumb_path,
                    reply_to_message_id=topic_id,
                    parse_mode=ParseMode.HTML,
                    progress=progress_bar,
                    progress_args=("╔══━⚡️Uploading...⚡️━══╗\n", edit, time.time())
                )

            # ✅ Fast log: copy already-uploaded message instead of re-uploading from disk
            log_file_msg = await dm.copy(LOG_GROUP)

            # ✅ Send log info separately as reply to log file
            await app.send_message(
                LOG_GROUP,
                text=log_caption,
                reply_to_message_id=log_file_msg.id,
                parse_mode=ParseMode.MARKDOWN
            )


        # ────── Telethon Upload ──────
        elif upload_method == "Telethon":
            await edit.delete()
            progress_message = await gf.send_message(sender, "**__Uploading...__**")
            # Caption is already HTML
            caption_html = caption

            uploaded = await fast_upload(
                gf, file,
                reply=progress_message,
                name=file_name,
                progress_bar_function=lambda done, total: progress_callback(done, total, sender)
            )
            await progress_message.delete()

            attributes = [
                DocumentAttributeVideo(duration=duration, w=width, h=height, supports_streaming=True)
            ] if ext in video_formats else []

            bot = await app.get_me()
            bot_name = f"{bot.first_name} (@{bot.username})" if bot else "Bot"

            log_caption = (
                f"📁 **File Name:** {file_name}\n\n"
                f"📤 **Upload Info**\n"
                f"👤 **User:** [{sender}](tg://user?id={sender})\n"
                f"🆔 **User ID:** `{sender}`\n"
                f"🗂️ **Type:** `{ext.upper()}`\n"

            )

            # Use already generated/retrieved thumb_path

            await gf.send_file(
                target_chat_id,
                uploaded,
                caption=caption_html,
                attributes=attributes,
                reply_to=topic_id,
                thumb=thumb_path
            )

            await gf.send_file(
                LOG_GROUP,
                uploaded,
                caption=log_caption,
                attributes=attributes,
                thumb=thumb_path
            )

    except Exception as e:
        await app.send_message(LOG_GROUP, f"❌ **Upload Failed:** `{str(e)}`")
        print(f"Error during media upload: {e}")

    finally:
    # Only delete if it was not from saved thumbnail
        if thumb_path and os.path.exists(thumb_path) and not thumb_path.startswith(THUMBNAIL_DIR):
            os.remove(thumb_path)
        gc.collect()



async def get_msg(userbot: TelegramClient, sender: int, edit_id: int, msg_link: str, i: int = 0, message: Message = None):
    try:
        # Sanitize the message link
        msg_link = msg_link.split("?single")[0]
        chat, msg_id = None, None
        saved_channel_ids = load_saved_channel_ids()
        upload_method = await fetch_upload_method(sender)
        size_limit = 2 * 1024 * 1024 * 1024  # 1.99 GB size limit
        file = ''
        edit = ''
        # Extract chat and message ID for various Telegram link formats
        if 't.me/c/' in msg_link or 't.me/b/' in msg_link:
            parts = [p for p in msg_link.split("/") if p]
            if 't.me/b/' in msg_link:
                chat = parts[-2]
                msg_id = int(parts[-1]) + i
            else:
                chat = int('-100' + parts[parts.index('c') + 1])
                msg_id = int(parts[-1]) + i
        elif 'tg://openmessage' in msg_link:
            import urllib.parse
            parsed_url = urllib.parse.urlparse(msg_link)
            params = urllib.parse.parse_qs(parsed_url.query)
            # Handle user_id, chat_id and id parameters
            chat_val = params.get("user_id", [None])[0] or params.get("chat_id", [None])[0] or params.get("id", [None])[0]
            msg_id = int(params.get("message_id", [0])[0]) + i
            if chat_val:
                chat_val = chat_val.strip()
                if chat_val.isdigit():
                    if len(chat_val) >= 10 and not chat_val.startswith("-100"):
                        chat = int("-100" + chat_val)
                    else:
                        chat = int(chat_val)
                elif chat_val.startswith("-"):
                    chat = int(chat_val)
                else:
                    chat = chat_val
            
            # Update processing message for private links
            edit = await app.edit_message_text(sender, edit_id, "Processing Private Link... 🔐")
            
            # Check if userbot is available
            if userbot is None:
                await edit.edit("Please login using /login to access private links.")
                return
        elif 't.me/' in msg_link or 'telegram.me/' in msg_link or 'telegram.dog/' in msg_link:
            if '/s/' in msg_link: # handles stories
                edit = await app.edit_message_text(sender, edit_id, "Story Link Detected...")
                if userbot is None:
                    await edit.edit("Login in bot to save stories...")     
                    return
                parts = [p for p in msg_link.split("/") if p]
                # parts: ['https:', 't.me', 's', 'chat_id', 'msg_id'] -> index 3 is chat_id
                chat = parts[3]
                if chat.isdigit():
                    chat = f"-100{chat}"
                msg_id = int(parts[-1])
                await download_user_stories(userbot, chat, msg_id, edit, sender)
                await edit.delete(2)
                return
            
            # Public links, Forum/Topic links
            # Link format: t.me/username/mid or t.me/username/topicid/mid
            # Split and filter empty parts
            domain = "t.me/" if "t.me/" in msg_link else "telegram.me/" if "telegram.me/" in msg_link else "telegram.dog/"
            parts = [p for p in msg_link.split(domain)[1].split("/") if p]
            if not parts:
                return
            chat = parts[0]
            msg_id = int(parts[-1]) + i
        else:
            chat = None
            msg_id = None

        if not chat or not msg_id:
            return

        # Check if the channel is protected
        if chat in saved_channel_ids:
            await app.edit_message_text(
                message.chat.id, edit_id,
                "This channel is protected by **__CHOSEN ONE ⚝__💀**.\nKya Be... Hamara Hi Content Nikalega 🌝 Kahi Or Try Kar 😘"
            )
            return

        # For public links, try copying first (faster/safer)
        if not ('t.me/c/' in msg_link or 't.me/b/' in msg_link or 'tg://openmessage' in msg_link):
            edit = await app.edit_message_text(sender, edit_id, "Processing link...🌝")
            copy_success = await copy_message_with_chat_id(app, userbot, sender, chat, msg_id, edit)
            if copy_success:
                await edit.delete(2)
                return
            # If copy fails, fallback to extraction logic below
            await edit.edit("**Copy failed, trying extraction...**")

        # Fetch the target message
        client = userbot if userbot else get_client() or app
        
        try:
            msg = await client.get_messages(chat, msg_id)
        except Exception as e:
            if userbot: # If userbot failed, try fallback
                client = get_client() or app
                msg = await client.get_messages(chat, msg_id)
            else:
                raise e
        
        if not msg or msg.service or msg.empty:
            return
        
        # Ensure extraction uses the same client
        userbot = client

        target_chat_id = user_chat_ids.get(message.chat.id, message.chat.id)
        topic_id = None
        if '/' in str(target_chat_id):
            target_chat_id, topic_id = map(int, target_chat_id.split('/', 1))

        # Handle different message types
        if msg.media == MessageMediaType.WEB_PAGE:
            if not await is_enabled(sender, "text"):
                return
            await clone_message(app, msg, target_chat_id, topic_id, edit_id, LOG_GROUP)
            return

        if msg.text:
            if not await is_enabled(sender, "text"):
                return
            await clone_text_message(app, msg, target_chat_id, topic_id, edit_id, LOG_GROUP)
            return

        if msg.sticker:
            await handle_sticker(app, msg, target_chat_id, topic_id, edit_id, LOG_GROUP)
            return

        
        # Handle file media (photo, document, video)
        file_size = get_message_file_size(msg)

        # if file_size and file_size > size_limit and pro is None:
        #     await app.edit_message_text(sender, edit_id, "**❌ 4GB Uploader not found**")
        #     return

        file_name = await get_media_filename(msg)
        edit = await app.edit_message_text(sender, edit_id, "**>Downloading...Darling 😘**")

        # Optimized Download media
        if upload_method == "Telethon":
            file = await fast_download(
                userbot, msg, edit, file_name,
                lambda done, total: progress_callback(done, total, sender)
            )
        else:
            file = await userbot.download_media(
                msg,
                file_name=file_name,            
                progress_args=("╔══━⚡️ Downloading ⚡️━══╗\n", edit, time.time()),
                progress=progress_bar
            )
        
        if not file:
            await edit.edit("❌ **Download failed** - The file might be corrupted or the bot's session has expired.")
            return

        caption = await get_final_caption(msg, sender)

        # Apply PDF Watermark if enabled
        if file.lower().endswith(".pdf"):
            data = await odb.get_data(sender)
            if data and data.get("pdf_watermark"):
                # Use custom watermark text if available, otherwise use rebrand tag, otherwise default
                watermark_to_use = data.get("watermark_text")
                if not watermark_to_use:
                    watermark_to_use = user_rename_preferences.get(str(sender), '@Chosen_Onex_bot')
                
                grid_val = data.get("pdf_grid", False)
                opacity_val = data.get("pdf_opacity", 0.12)
                
                await edit.edit(f"🛡️ **Adding {'Grid' if grid_val else 'Diagonal'} Watermark...**")
                watermarked_file = await add_pdf_watermark(file, watermark_to_use, grid=grid_val, opacity=opacity_val)
                if watermarked_file != file:
                    if os.path.exists(file):
                        os.remove(file)
                    file = watermarked_file

        # Rename file
        file = await rename_file(file, sender)
        if msg.audio:
            if not await is_enabled(sender, "audio"):
                return
            result = await app.send_audio(target_chat_id, file, caption=caption, reply_to_message_id=topic_id)
            await result.copy(LOG_GROUP)
            await edit.delete(1)
            return
        
        if msg.voice:
            result = await app.send_voice(target_chat_id, file, reply_to_message_id=topic_id)
            await result.copy(LOG_GROUP)
            await edit.delete(1)
            return

        if msg.photo:
            if not await is_enabled(sender, "photo"):
                return
            result = await app.send_photo(target_chat_id, file, caption=None, reply_to_message_id=topic_id)
            await result.copy(LOG_GROUP)
            await edit.delete(1)
            return

        # Upload media
        # await edit.edit("**Checking file...**")
        if msg.video and not await is_enabled(sender, "video"):
            return
        if msg.document and not await is_enabled(sender, "document"):
            return

        free_check = await chk_user(message, sender)
        if file_size > size_limit and (free_check == 0 or pro is None):
            await edit.delete()
            await split_and_upload_file(app, sender, target_chat_id, file, caption, topic_id)
            return
        elif file_size > size_limit:
            await handle_large_file(file, sender, edit, caption)
        else:
            await upload_media(sender, target_chat_id, file, caption, edit, topic_id)

    except (ChannelBanned, ChannelInvalid, ChannelPrivate, ChatIdInvalid, ChatInvalid):
        await app.edit_message_text(sender, edit_id, "🌚 First do /login & then send me the Link again send /guide for more help")
    except Exception as e:
        if edit:
            try:
                await edit.edit(f"Failed to process: `{msg_link}`\n\n**Error:** {str(e)}")
            except:
                pass
        print(f"Error: {e}")
    finally:
        # Clean up
        if file and os.path.exists(file):
            os.remove(file)
        if edit:
            await edit.delete(1)
        
async def clone_message(app, msg, target_chat_id, topic_id, edit_id, log_group):
    edit = await app.edit_message_text(target_chat_id, edit_id, "Cloning...")
    devgaganin = await app.send_message(target_chat_id, msg.text.markdown, reply_to_message_id=topic_id)
    await devgaganin.copy(log_group)
    await edit.delete()

async def clone_text_message(app, msg, target_chat_id, topic_id, edit_id, log_group):
    edit = await app.edit_message_text(target_chat_id, edit_id, "Cloning text message...")
    devgaganin = await app.send_message(target_chat_id, msg.text.markdown, reply_to_message_id=topic_id)
    await devgaganin.copy(log_group)
    await edit.delete()


async def handle_sticker(app, msg, target_chat_id, topic_id, edit_id, log_group):
    edit = await app.edit_message_text(target_chat_id, edit_id, "Handling sticker...")
    result = await app.send_sticker(target_chat_id, msg.sticker.file_id, reply_to_message_id=topic_id)
    await result.copy(log_group)
    await edit.delete()




async def get_media_filename(msg):
    if msg.document:
        return msg.document.file_name or "Document.txt"
    if msg.video:
        return msg.video.file_name or "Video.mp4"
    if msg.audio:
        return msg.audio.file_name or "Audio.mp3"
    if msg.photo:
        return "Image.jpg"
    return "File.dat"



def get_message_file_size(msg):
    if msg.document:
        return msg.document.file_size
    if msg.photo:
        return msg.photo.file_size
    if msg.video:
        return msg.video.file_size
    return 1



async def get_final_caption(msg, sender):
    # Get user data from DB
    user_data = await odb.get_data(sender)
    
    # Get custom caption from DB
    custom_caption = user_data.get("caption") if user_data else ""
    
    # Get active tag for cleaning and display
    active_tag = user_data.get("active_tag", "@Chosen_Onex_bot") if user_data else "@Chosen_Onex_bot"
    
    # Get original caption in HTML format to preserve blockquotes and other formatting
    original_caption = msg.caption.html if msg.caption else ""
    
    # Clean original caption with the user's active tag and custom word filters
    delete_words = user_data.get("delete_words", []) if user_data else []
    replacements = user_data.get("replacement_words", {}) if user_data else {}
    cleaned_original = clean_text_advanced(original_caption, active_tag, delete_words, replacements)
    
    if custom_caption:
        # Use user's custom caption template
        if "{caption}" in custom_caption:
            final_text = custom_caption.replace("{caption}", cleaned_original)
        else:
            final_text = f"{cleaned_original}\n\n{custom_caption}"
    else:
        # Just use the cleaned original text as is
        final_text = cleaned_original

    # Final HTML formatting support
    return format_caption_to_html(final_text)



async def download_user_stories(userbot, chat_id, msg_id, edit, sender):
    try:
        # Fetch the story using the provided chat ID and message ID
        story = await userbot.get_stories(chat_id, msg_id)
        if not story:
            await edit.edit("No story available for this user.")
            return  
        if not story.media:
            await edit.edit("The story doesn't contain any media.")
            return
        await edit.edit("Downloading Story...")
        file_path = await userbot.download_media(story)
        print(f"Story downloaded: {file_path}")
        # Send the downloaded story based on its type
        if story.media:
            await edit.edit("Uploading Story...")
            if story.media == MessageMediaType.VIDEO:
                await app.send_video(sender, file_path)
            elif story.media == MessageMediaType.DOCUMENT:
                await app.send_document(sender, file_path)
            elif story.media == MessageMediaType.PHOTO:
                await app.send_photo(sender, file_path)
        if file_path and os.path.exists(file_path):
            os.remove(file_path)  
        await edit.edit("Story processed successfully.")
    except RPCError as e:
        print(f"Failed to fetch story: {e}")
        await edit.edit(f"Error: {e}")
        
async def copy_message_with_chat_id(app, userbot, sender, chat_id, message_id, edit):
    target_chat_id = user_chat_ids.get(sender, sender)
    file = None
    result = None
    size_limit = 2 * 1024 * 1024 * 1024  # 2 GB size limit

    try:
        # Try with app or fallback client
        client_to_use = app
        try:
            msg = await client_to_use.get_messages(chat_id, message_id)
            if not msg or msg.empty:
                raise Exception("Message not found")
        except Exception:
            client_to_use = get_client()
            if client_to_use:
                msg = await client_to_use.get_messages(chat_id, message_id)
            else:
                return False

        if not msg or msg.empty:
            return False

        # If PDF Watermarking is ON, we MUST extract (don't use copy)
        data_stored = await odb.get_data(sender)
        is_pdf = msg.document and msg.document.file_name and msg.document.file_name.lower().endswith(".pdf")
        if data_stored and data_stored.get("pdf_watermark") and is_pdf:
            return False

        final_caption = await get_final_caption(msg, sender)

        topic_id = None
        if '/' in str(target_chat_id):
            target_chat_id, topic_id = map(int, target_chat_id.split('/', 1))

        # Use copy_message for EVERYTHING (media + text) - it's fast and handles server-side copy
        result = await app.copy_message(
            chat_id=target_chat_id,
            from_chat_id=chat_id,
            message_id=message_id,
            caption=final_caption,
            reply_to_message_id=topic_id,
            parse_mode=ParseMode.HTML
        )
        
        if result:
            return True

    except Exception as e:
        print(f"App copy failed: {e}")

    # Fallback to userbot if app copy fails
    if userbot:
        try:
            await edit.edit("Trying extraction via userbot... ⚡")
            
            # Resolve chat_id if it's a username string
            if isinstance(chat_id, str) and not chat_id.startswith("-") and not chat_id.isdigit():
                try:
                    chat_entity = await userbot.get_entity(chat_id)
                    resolved_chat_id = chat_entity.id
                except Exception:
                    resolved_chat_id = chat_id
            else:
                resolved_chat_id = chat_id

            msg = await userbot.get_messages(resolved_chat_id, message_id)
            if not msg or msg.empty:
                return False

            if msg.text:
                await app.send_message(target_chat_id, msg.text.markdown, reply_to_message_id=topic_id)
                return True

            custom_caption = get_user_caption_preference(sender)
            final_caption = format_caption(msg.caption.markdown if msg.caption else "", sender, custom_caption)
            
            file = await userbot.download_media(
                msg,
                progress=progress_bar,
                progress_args=("╭─────────────────────╮\n│      **__Downloading__...**\n├─────────────────────", edit, time.time())
            )
            if not file:
                return False

            file = await rename_file(file, sender)
            file_size = os.path.getsize(file)

            if msg.photo:
                await app.send_photo(target_chat_id, file, caption=None, reply_to_message_id=topic_id)
            elif msg.video or msg.document:
                freecheck = await chk_user(None, sender)
                if file_size > size_limit and (freecheck == 0 or pro is None):
                    await split_and_upload_file(app, sender, target_chat_id, file, final_caption, topic_id)
                elif file_size > size_limit:
                    await handle_large_file(file, sender, edit, final_caption)
                else:
                    await upload_media(sender, target_chat_id, file, final_caption, edit, topic_id)
            elif msg.audio:
                await app.send_audio(target_chat_id, file, caption=final_caption, reply_to_message_id=topic_id)
            elif msg.voice:
                await app.send_voice(target_chat_id, file, reply_to_message_id=topic_id)
            elif msg.sticker:
                await app.send_sticker(target_chat_id, msg.sticker.file_id, reply_to_message_id=topic_id)
            
            return True
        except Exception as e:
            print(f"Userbot extraction failed: {e}")
            return False
        finally:
            if file and os.path.exists(file):
                os.remove(file)
    
    return False

async def send_media_message(app, target_chat_id, msg, caption, topic_id):
    try:
        file_name = None

        # Try to get file name if available
        if msg.document and msg.document.file_name:
            file_name = msg.document.file_name
        elif msg.video and msg.video.file_name:
            file_name = msg.video.file_name

        # Caption handling
        if caption:
            # If caption exists → keep it same, just remove links if needed
            caption = re.sub(
                r'https?://t\.me/[^\s]+|https?://telegram\.me/[^\s]+',
                '',
                caption
            )
        elif file_name:
            # If no caption → use only file name
            caption = f"🗃 {file_name}"
        else:
            # If nothing → fallback
            caption = "@II_LevelUP_II"

        # Send the message with the right method
        if msg.video:
            return await app.send_video(
                target_chat_id,
                msg.video.file_id,
                caption=caption,
                reply_to_message_id=topic_id,
            )

        if msg.document:
            return await app.send_document(
                target_chat_id,
                msg.document.file_id,
                caption=caption,
                reply_to_message_id=topic_id,
            )

        if msg.photo:
            return await app.send_photo(
                target_chat_id,
                msg.photo.file_id,
                caption=None,
                reply_to_message_id=topic_id,
            )

    except Exception as e:
        print(f"Error while sending media: {e}")
        return await app.send_message(
            target_chat_id,
            f"❌ Failed to send media.\n\nError: {e}"
        )



#CUSTOM_EMOJIS = ["🍁", "🍀", "👑", "✨", "🦋", "🌟", "💖"]

def replace_fancy_and_emoji(text: str) -> str:
    """
    Remove fancy Unicode characters (like 𝐀–𝒁, 𓆩𓆪, etc.)
    Replace emojis (symbols) with our custom emoji set.
    """
    result = []
    for char in text:
        code = ord(char)

        # Skip fancy styled alphabets (Mathematical, etc.)
        if (0x1D400 <= code <= 0x1D7FF) or (0x13000 <= code <= 0x1342F):
            continue

        # Replace emojis or symbolic characters
        if unicodedata.category(char) == "So" or char in ['️', '‍', '\u200d']:
            result.append(random.choice(CUSTOM_EMOJIS))
        else:
            result.append(char)

    return ''.join(result)

def format_caption(original_caption, sender, custom_caption):
    # Fetch active tag for this user
    user_data = collection.find_one({"_id": sender})
    user_tag = user_data.get("active_tag", "@Chosen_Onex_bot") if user_data else "@Chosen_Onex_bot"
    delete_words = user_data.get("delete_words", []) if user_data else []
    replacements = user_data.get("replacement_words", {}) if user_data else {}
    
    if not original_caption:
        original_caption = ""

    # Clean unwanted phrases
    original_caption = clean_text_advanced(original_caption, user_tag, delete_words, replacements)

    # ✅ Remove all hashtags like #Movie
    original_caption = re.sub(r'#\S+', '', original_caption)

    # ✅ Replace telegram links with a clean placeholder or keep them
    # Removed hardcoded spam link
    original_caption = re.sub(
        r'https?://(t\.me|telegram\.me)/[^\s]+',
        '',
        original_caption
    )

    # ✅ Replace "Extracted By" with custom credit    
    original_caption = re.sub(
        r'(📩)?\s*(Extracted[\s_]*By)\s*[:➤>–\-]*\s*.*',

        r'\n\n**🖤 Sᴛꪮʟᴇɴ Hᴀᴘᴘɪɴᴇss ⚝**',
        original_caption,
        flags=re.IGNORECASE
    )



    # ✅ Replace "Downloaded By" with bot handle
    original_caption = re.sub(
        r'(📩)?\s*(Downloaded[\s_]*By)\s*[:➤>–\-]*\s*.*',

        r'**❉ Sᴛꪮʟᴇɴ Hᴀᴘᴘɪɴᴇss**',
        original_caption,
        flags=re.IGNORECASE
    )

    
    original_caption = re.sub(
        r'(⏫)?\s*<u>?\s*(Uploaded[\s_]*By)\s*[➤:>–\-]*\s*[^<\n]+</u>?',
        r'⏫ Uploaded By ➤ Sᴛꪮʟᴇɴ Hᴀᴘᴘɪɴᴇss',
        original_caption,
        flags=re.IGNORECASE
        )

    # Symbols and other cleaning
    original_caption = original_caption.replace("[", "〘").replace("]", "〙")
    original_caption = original_caption.replace("📕", "📓")
    original_caption = original_caption.replace("📽️", "🍀")

    # ✅ Append custom caption if exists
    if custom_caption:
        return f"{original_caption}\n\n__**{custom_caption}**__"
    return original_caption

# ------------------------ Button Mode Editz FOR SETTINGS ----------------------------

# Define a dictionary to store user chat IDs
user_chat_ids = {}

def load_user_data(user_id, key, default_value=None):
    try:
        user_data = collection.find_one({"_id": user_id})
        return user_data.get(key, default_value) if user_data else default_value
    except Exception as e:
     
        print(f"Error loading {key}: {e}")
        return default_value

def load_saved_channel_ids():
    saved_channel_ids = set()
    try:
        # Retrieve channel IDs from MongoDB collection
        for channel_doc in collection.find({"channel_id": {"$exists": True}}):
            saved_channel_ids.add(channel_doc["channel_id"])
    except Exception as e:
        print(f"Error loading saved channel IDs: {e}")
    return saved_channel_ids

def save_user_data(user_id, key, value):
    try:
        collection.update_one(
            {"_id": user_id},
            {"$set": {key: value}},
            upsert=True
        )
    except Exception as e:
        print(f"Error saving {key}: {e}")


# Delete and replacement word functions
load_delete_words = lambda user_id: set(load_user_data(user_id, "delete_words", []))
save_delete_words = lambda user_id, words: save_user_data(user_id, "delete_words", list(words))

load_replacement_words = lambda user_id: load_user_data(user_id, "replacement_words", {})
save_replacement_words = lambda user_id, replacements: save_user_data(user_id, "replacement_words", replacements)

# User session functions
def load_user_session(user_id):
    return load_user_data(user_id, "session")

# Upload preference functions
set_dupload = lambda user_id, value: save_user_data(user_id, "dupload", value)
get_dupload = lambda user_id: load_user_data(user_id, "dupload", False)

# User preferences storage
user_rename_preferences = {}
user_caption_preferences = {}

# Rename and caption preference functions
async def set_rename_command(user_id, custom_rename_tag):
    user_rename_preferences[str(user_id)] = custom_rename_tag

get_user_rename_preference = lambda user_id: user_rename_preferences.get(str(user_id), '⛥ @II_LevelUp_II')

async def set_caption_command(user_id, custom_caption):
    await odb.update_data(user_id, {"caption": custom_caption})

get_user_caption_preference = lambda user_id: user_caption_preferences.get(str(user_id), '')

# Initialize the dictionary to store user sessions

sessions = {}
m = None
SET_PIC = "settings.jpg"
MESS = "Customize settings ..."

@gf.on(events.NewMessage(incoming=True, pattern='/settings'))
async def settings_command(event):
    user_id = event.sender_id
    await send_settings_message(event.chat_id, user_id)

async def send_settings_message(chat_id, user_id):
    # Fetch current user data for filters status
    data = await odb.get_data(user_id)
    filters = data.get("filters", {}) if data else {}
    
    buttons = [
        [Button.inline("💀 Forward to Chat", b'setchat'), Button.inline("🏷️ Manage Tags", b'tag_manager')],
        [Button.inline("✏️ Set Rename Tag", b'setrename'), Button.inline("🔆 Set Caption", b'setcaption')],
        [Button.inline("💠 Replace Words", b'setreplacement'), Button.inline("🗑️ Remove Words", b'delete')],
        [Button.inline("🎭 Media Filters", b'filters'), Button.inline("📄 PDF Settings", b'pdf_settings')],
        [Button.inline("🖼️ Set Thumbnail", b'setthumb'), Button.inline("🧲 Remove Thumbnail", b'remthumb')],
        [Button.inline("📤 Upload Method", b'uploadmethod'), Button.inline("⛔ Logout", b'logout')],
        [Button.inline("♻️ Reset All Settings ☢️", b'reset')],
        [Button.url("💞 Contact Owner 🦋", "https://t.me/Chosen_Onex_bo")]
    ]
    
    await gf.send_file(
        chat_id,
        file=SET_PIC,
        caption=MESS,
        buttons=buttons
    )

async def send_filter_menu(event, user_id):
    data = await odb.get_data(user_id)
    filters = data.get("filters", {}) if data else {}
    
    def get_status(m_type):
        return "🟢 ON" if filters.get(m_type, True) else "🔴 OFF"

    buttons = [
        [Button.inline(f"Video: {get_status('video')}", b'toggle_video'), Button.inline(f"Audio: {get_status('audio')}", b'toggle_audio')],
        [Button.inline(f"Document: {get_status('document')}", b'toggle_document'), Button.inline(f"Photo: {get_status('photo')}", b'toggle_photo')],
        [Button.inline("⬅️ Back", b'back_to_settings')]
    ]
    
    await event.edit("🎭 **Media Filters**\n\nChoose which media types you want the bot to process:", buttons=buttons)

async def send_pdf_settings(event, user_id):
    data = await odb.get_data(user_id)
    pdf_watermark = data.get("pdf_watermark", False) if data else False
    grid_mode = data.get("pdf_grid", False) if data else False
    opacity = data.get("pdf_opacity", 0.12) if data else 0.12
    
    status = "🟢 Enabled" if pdf_watermark else "🔴 Disabled"
    mode_text = "🔳 Grid Mode" if grid_mode else "🎯 Single Mode"
    opacity_text = f"💡 Opacity: {int(opacity * 100)}%"
    custom_text = data.get("watermark_text", "Default Tag") if data else "Default Tag"
    
    buttons = [
        [Button.inline(f"Status: {status}", b'toggle_pdf_watermark')],
        [Button.inline(f"Style: {mode_text}", b'toggle_pdf_grid')],
        [Button.inline(f"Opacity: {opacity_text}", b'cycle_pdf_opacity')],
        [Button.inline(f"🖋️ Set Text: {custom_text}", b'set_pdf_text')],
        [Button.inline("⬅️ Back to Menu", b'back_to_settings')]
    ]
    
    msg = (
        "📄 **Premium PDF Branding**\n\n"
        f"🛡️ **Current Text**: `{custom_text}`\n"
        f"🎨 **Style**: `{'Repeating Grid' if grid_mode else 'Central Diagonal'}`\n"
        f"✨ **Visibility**: `{int(opacity*100)}% Transparent`\n\n"
        "Configure your professional PDF watermark settings below:"
    )
    await event.edit(msg, buttons=buttons)


pending_photos = {}

async def send_tag_manager(event, user_id):
    data = await odb.get_data(user_id)
    tag_list = data.get("tag_list", []) if data else []
    active_tag = data.get("active_tag", "@Chosen_Onex_bot") if data else "@Chosen_Onex_bot"
    
    msg = f"🏷️ **Tag Manager**\n\n**Active Tag**: `{active_tag}`\n\nYour saved tags:\n"
    buttons = []
    
    if not tag_list:
        msg += "_No tags saved yet._"
    else:
        for i, tag in enumerate(tag_list):
            msg += f"{i+1}. `{tag}`\n"
            # Limit to 10 tags for UI sanity
            if i < 10:
                buttons.append([
                    Button.inline(f"✅ Use {tag[:15]}...", f"select_tag_{i}".encode()),
                    Button.inline(f"🗑️", f"del_tag_{i}".encode())
                ])
    
    buttons.append([Button.inline("➕ Add New Tag", b'add_tag')])
    buttons.append([Button.inline("⬅️ Back", b'back_to_settings')])
    
    await event.edit(msg, buttons=buttons)

@gf.on(events.CallbackQuery)
async def callback_query_handler(event):
    user_id = event.sender_id
    data = event.data.decode() if isinstance(event.data, bytes) else event.data

    if data == 'setchat':
        await event.respond(
            "🎯 **Set Your Channel or Group**\n\n"
            "🆔 **Send the Chat ID** where you want to forward all posts automatically. 🌝\n\n"
            "💡 *Tip:* Just **add me to that chat**, then send `/id` in the Channel/Group.\n"
            "**I'll automatically detect the Chat ID.**"
        )
        sessions[user_id] = 'setchat'
    
    elif data == 'setrename':
        await event.respond("✏️ Send the **rename tag** you want to set your custom name")
        sessions[user_id] = 'setrename'

    elif data == 'tag_manager':
        await send_tag_manager(event, user_id)

    elif data == 'add_tag':
        await event.respond("🖋️ Send the **Tag** (e.g. `@MyBot`) you want to add to your list:")
        sessions[user_id] = 'addnewtag'

    elif data.startswith('select_tag_'):
        index = int(data.split('_')[-1])
        data_stored = await odb.get_data(user_id)
        tag_list = data_stored.get("tag_list", [])
        if index < len(tag_list):
            new_active = tag_list[index]
            await odb.update_data(user_id, {"active_tag": new_active})
            await event.answer(f"✅ Tag set to: {new_active}")
            await send_tag_manager(event, user_id)

    elif data.startswith('del_tag_'):
        index = int(data.split('_')[-1])
        data_stored = await odb.get_data(user_id)
        tag_list = data_stored.get("tag_list", [])
        if index < len(tag_list):
            removed = tag_list.pop(index)
            await odb.update_data(user_id, {"tag_list": tag_list})
            await event.answer(f"🗑️ Removed: {removed}")
            await send_tag_manager(event, user_id)

    elif data == 'setcaption':
        await event.respond("📝 Send the **caption format** (you can include variables like {filename}, {size}):")
        sessions[user_id] = 'setcaption'

    elif data == 'setreplacement':
        await event.respond("🔄 Send replacement inside this ' '\n\n'oldword' 'newword'\n\n")
        sessions[user_id] = 'setreplacement'

    elif data == 'addsession':
        await event.respond("🔐 Send your **Pyrogram V2 session string**:\n\n*(We recommend not sharing this publicly)*")
        sessions[user_id] = 'addsession'

    elif data == 'delete':
        await event.respond("🗑️ Send **words to delete** (separated by space) from the filename/caption:")
        sessions[user_id] = 'deleteword'

    elif data == 'logout':
        await odb.remove_session(user_id)
        user_data = await odb.get_data(user_id)
        if user_data and user_data.get("session") is None:
            await event.respond("✅ You have been **logged out** and your session was removed successfully.")
        else:
            await event.respond("⚠️ You are not logged in.")

    elif data == 'setthumb':
        pending_photos[user_id] = True
        await event.respond("📸 Send the **photo** you want to use as your custom thumbnail.")

    elif event.data == b'uploadmethod':
        # Retrieve the user's current upload method (default to Pyrogram)
        user_data = collection.find_one({'user_id': user_id})
        current_method = user_data.get('upload_method', 'Pyrogram') if user_data else 'Pyrogram'
        pyrogram_check = " ✅" if current_method == "Pyrogram" else ""
        telethon_check = " ✅" if current_method == "Telethon" else ""

        # Display the buttons for selecting the upload method
        buttons = [
            [Button.inline(f"II_LevelUP_II v1 ⚡{pyrogram_check}", b'pyrogram')],
            [Button.inline(f"⚠️ Coming soon V2 {telethon_check}", b'telethon')]
        ]
        await event.edit("Choose your preferred upload method:\n\n__**Note:** **II_LevelUP_II v2 ⚡**, built on Telethon(base), by @II_LevelUP_II still in beta.__", buttons=buttons)

    elif event.data == b'pyrogram':
        save_user_upload_method(user_id, "Pyrogram")
        await event.edit("Upload method set to **Pyrogram** ✅")

    elif event.data == b'telethon':
        save_user_upload_method(user_id, "Telethon")
        await event.edit("Upload method set to **II_LevelUP_II V2 ⚡ \n\n Use V1 V2 is just Testing purpose**")        
        
    elif event.data == b'reset':
        try:
            user_id_str = str(user_id)
            
            collection.update_one(
                {"_id": user_id},
                {"$unset": {
                    "delete_words": "",
                    "replacement_words": "",
                    "watermark_text": "",
                    "duration_limit": ""
                }}
            )
            
            collection.update_one(
                {"user_id": user_id},
                {"$unset": {
                    "delete_words": "",
                    "replacement_words": "",
                    "watermark_text": "",
                    "duration_limit": ""
                }}
            )            
            user_chat_ids.pop(user_id, None)
            user_rename_preferences.pop(user_id_str, None)
            user_caption_preferences.pop(user_id_str, None)
            thumbnail_path = os.path.join(THUMBNAIL_DIR, f"{user_id}.jpg")
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
            await event.respond("✅ Reset successfully, to logout click /logout")
        except Exception as e:
            await event.respond(f"Error clearing delete list: {e}")
    
    elif data == 'filters':
        await send_filter_menu(event, user_id)

    elif data.startswith('toggle_'):
        media_type = data.split('_')[1]
        data_stored = await odb.get_data(user_id)
        filters = data_stored.get("filters", {}) if data_stored else {}
        filters[media_type] = not filters.get(media_type, True)
        await odb.update_data(user_id, {"filters": filters})
        await send_filter_menu(event, user_id)

    elif data == 'pdf_settings':
        await send_pdf_settings(event, user_id)

    elif data == 'set_pdf_text':
        await event.respond("🖋️ Send the **Text** you want to use as a PDF watermark:")
        sessions[user_id] = 'setpdfwatermark'

    elif data == 'toggle_pdf_watermark':
        data_stored = await odb.get_data(user_id)
        current = data_stored.get("pdf_watermark", False) if data_stored else False
        await odb.update_data(user_id, {"pdf_watermark": not current})
        await send_pdf_settings(event, user_id)

    elif data == 'toggle_pdf_grid':
        data_stored = await odb.get_data(user_id)
        current = data_stored.get("pdf_grid", False) if data_stored else False
        await odb.update_data(user_id, {"pdf_grid": not current})
        await send_pdf_settings(event, user_id)

    elif data == 'cycle_pdf_opacity':
        data_stored = await odb.get_data(user_id)
        current = data_stored.get("pdf_opacity", 0.12) if data_stored else 0.12
        # Cycle through 0.12 -> 0.3 -> 0.6 -> 0.12
        if current < 0.2:
            new_val = 0.3
        elif current < 0.4:
            new_val = 0.6
        else:
            new_val = 0.12
        await odb.update_data(user_id, {"pdf_opacity": new_val})
        await send_pdf_settings(event, user_id)

    elif data == 'back_to_settings':
        # Re-send main settings menu
        buttons = [
            [Button.inline("💀 Forward to Chat", b'setchat'), Button.inline("🏷️ Manage Tags", b'tag_manager')],
            [Button.inline("✏️ Set Rename Tag", b'setrename'), Button.inline("🔆 Set Caption", b'setcaption')],
            [Button.inline("💠 Replace Words", b'setreplacement'), Button.inline("🗑️ Remove Words", b'delete')],
            [Button.inline("🎭 Media Filters", b'filters'), Button.inline("📄 PDF Settings", b'pdf_settings')],
            [Button.inline("🖼️ Set Thumbnail", b'setthumb'), Button.inline("🧲 Remove Thumbnail", b'remthumb')],
            [Button.inline("📤 Upload Method", b'uploadmethod'), Button.inline("⛔ Logout", b'logout')],
            [Button.inline("♻️ Reset All Settings ☢️", b'reset')],
            [Button.url("💞 Contact Owner 🦋", "https://t.me/Chosen_Onex_bo")]
        ]
        await event.edit(MESS, buttons=buttons)

    elif event.data == b'remthumb':
        try:
            thumbnail_path = os.path.join(THUMBNAIL_DIR, f"{user_id}.jpg")
            os.remove(thumbnail_path)
            await event.respond('Thumbnail removed successfully!')
        except FileNotFoundError:
            await event.respond("No thumbnail found to remove.")
    

@gf.on(events.NewMessage(func=lambda e: e.sender_id in pending_photos))
async def save_thumbnail(event):
    user_id = event.sender_id  # Use event.sender_id as user_id

    if event.photo:
        thumbnail_path = os.path.join(THUMBNAIL_DIR, f"{user_id}.jpg")
        await event.download_media(file=thumbnail_path)
        await event.respond('✅ **Custom thumbnail saved successfully!**')
    else:
        await event.respond('❌ Please send a **photo** to set it as a thumbnail.')

    # Remove user from pending photos dictionary in both cases
    pending_photos.pop(user_id, None)

def save_user_upload_method(user_id, method):
    # Save or update the user's preferred upload method
    collection.update_one(
        {'user_id': user_id},  # Query
        {'$set': {'upload_method': method}},  # Update
        upsert=True  # Create a new document if one doesn't exist
    )

@gf.on(events.NewMessage)
async def handle_user_input(event):
    user_id = event.sender_id
    if user_id in sessions:
        session_type = sessions[user_id]

        if session_type == 'setchat':
            try:
                chat_id = event.text
                user_chat_ids[user_id] = chat_id
                await event.respond("Chat ID set successfully! ✅ Now i will Forward All Content in That Chat")
            except ValueError:
                await event.respond("Invalid chat ID! Send valid chat id starting with -100xxxxxxxx")
                
        elif session_type == 'setrename':
            custom_rename_tag = event.text
            await set_rename_command(user_id, custom_rename_tag)
            await event.respond(f"😉 Your Custom rename tag set to: {custom_rename_tag} 🌝")

        elif session_type == 'addnewtag':
            new_tag = event.text
            data_stored = await odb.get_data(user_id)
            tag_list = data_stored.get("tag_list", []) if data_stored else []
            if new_tag not in tag_list:
                tag_list.append(new_tag)
                await odb.update_data(user_id, {"tag_list": tag_list, "active_tag": new_tag})
                await event.respond(f"✅ Tag `{new_tag}` added and set as active!")
            else:
                await event.respond("⚠️ This tag is already in your list.")
        
        elif session_type == 'setpdfwatermark':
            pdf_text = event.text
            await odb.update_data(user_id, {"watermark_text": pdf_text})
            await event.respond(f"📄 PDF Watermark text set to: `{pdf_text}` ✅")
        
        elif session_type == 'setcaption':
            custom_caption = event.text
            await set_caption_command(user_id, custom_caption)
            await event.respond(f"Custom caption set to: {custom_caption}")

        elif session_type == 'setreplacement':
            match = re.match(r"'(.+)' '(.+)'", event.text)
            if not match:
                await event.respond("Usage: 'Oldword(S)' 'ReplaceWord'\n\n **Example:** 'apple' 'banana'")
            else:
                word, replace_word = match.groups()
                delete_words = load_delete_words(user_id)
                if word in delete_words:
                    await event.respond(f"The word '{word}' is in the delete set and cannot be replaced.")
                else:
                    replacements = load_replacement_words(user_id)
                    replacements[word] = replace_word
                    save_replacement_words(user_id, replacements)
                    await event.respond(f"⇆ Replacement saved ⇆ \n\n 🌚 {word} ≫ {replace_word} 🌝")

        elif session_type == 'addsession':
            session_string = event.text
            await odb.set_session(user_id, session_string)
            await event.respond("✅ Session string added successfully!")
                
        elif session_type == 'deleteword':
            words_to_delete = event.message.text.split()
            delete_words = load_delete_words(user_id)
            delete_words.update(words_to_delete)
            save_delete_words(user_id, delete_words)
            await event.respond(f"🗑️ Words added to delete list: {', '.join(words_to_delete)}")
               
            
        del sessions[user_id]
    
# Command to store channel IDs
@gf.on(events.NewMessage(incoming=True, pattern='/lock'))
async def lock_command_handler(event):
    if event.sender_id not in OWNER_ID:
        return await event.respond("You are not authorized to use this command.😘 its only for my owner")
    
    # Extract the channel ID from the command
    try:
        channel_id = int(event.text.split(' ')[1])
    except (ValueError, IndexError):
        return await event.respond("Invalid /lock command. Use /lock CHANNEL_ID.")
    
    # Save the channel ID to the MongoDB database
    try:
        # Insert the channel ID into the collection
        collection.insert_one({"channel_id": channel_id})
        await event.respond(f"Channel ID {channel_id} locked successfully.")
    except Exception as e:
        await event.respond(f"Error occurred while locking channel ID: {str(e)}")


async def handle_large_file(file, sender, edit, caption):
    if pro is None:
        await edit.edit('**__ ❌ 4GB trigger not found__**')
        os.remove(file)
        gc.collect()
        return
    
    dm = None
    
    print("4GB connector found.")
    await edit.edit('**__ ✅ 4GB trigger connected...__**\n\n')
    
    target_chat_id = user_chat_ids.get(sender, sender)
    file_extension = str(file).split('.')[-1].lower()
    metadata = video_metadata(file)
    duration = metadata['duration']
    width = metadata['width']
    height = metadata['height']
    
    # ✅ Handle thumbnail
    thumb_path = thumbnail(sender)
    if not thumb_path and file_extension in VIDEO_EXTENSIONS:
        thumb_path = await screenshot(file, duration, sender)
    try:
        if file_extension in VIDEO_EXTENSIONS:
            dm = await pro.send_video(
                LOG_GROUP,
                video=file,
                caption=caption,
                thumb=thumb_path,
                height=height,
                width=width,
                duration=duration,
                progress=progress_bar,
                progress_args=(
                    "╭─────────────────────╮\n│       **__4GB Uploader__ ⚡**\n├─────────────────────",
                    edit,
                    time.time()
                )
            )
        else:
            # Send as document
            dm = await pro.send_document(
                LOG_GROUP,
                document=file,
                caption=caption,
                thumb=thumb_path,
                progress=progress_bar,
                progress_args=(
                    "╭─────────────────────╮\n│      **__4GB Uploader ⚡__**\n├─────────────────────",
                    edit,
                    time.time()
                )
            )

        from_chat = dm.chat.id
        msg_id = dm.id
        freecheck = 0
        if freecheck == 1:
            reply_markup = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("💎 Get Premium to Forward", url="https://t.me/GeniusJunctionX")]
                ]
            )
            await app.copy_message(
                target_chat_id,
                from_chat,
                msg_id,
                protect_content=True,
                reply_markup=reply_markup
            )
        else:
            # Simple copy without protect_content or reply_markup
            await app.copy_message(
                target_chat_id,
                from_chat,
                msg_id
            )
            
    except Exception as e:
        print(f"Error while sending file: {e}")

    finally:
        await edit.delete()
        if os.path.exists(file):
            os.remove(file)
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)
        gc.collect()


def strip_unicode_junk(text: str) -> str:
    """Remove stylized junk but preserve Indian language text and matras like ી િ ુ ે ા ૂ ૌ."""
    clean = []
    for char in text:
        codepoint = ord(char)
        name = unicodedata.name(char, "")

        # ✅ Preserve Gujarati & Indian scripts including matras
        if (
            0x0900 <= codepoint <= 0x097F or  # Devanagari
            0x0A80 <= codepoint <= 0x0AFF or  # Gujarati
            0x0980 <= codepoint <= 0x09FF or  # Bengali
            0x0B80 <= codepoint <= 0x0BFF or  # Tamil
            0x0C00 <= codepoint <= 0x0C7F or  # Telugu
            0x0C80 <= codepoint <= 0x0CFF or  # Kannada
            0x0D00 <= codepoint <= 0x0D7F     # Malayalam
        ):
            clean.append(char)
            continue

        # ✅ Preserve basic Latin and digits
        if (
            0x0020 <= codepoint <= 0x007E or
            0x00A0 <= codepoint <= 0x00FF
        ):
            if any(x in name for x in [
                'BOLD', 'ITALIC', 'SCRIPT', 'FRAKTUR', 'DOUBLE-STRUCK', 'CIRCLED', 'TAG'
            ]):
                continue
            clean.append(char)
            continue

        # ✅ Allow some safe symbols
        if char in (' ', '.', '-', '_', '(', ')', '[', ']'):
            clean.append(char)

    result = ''.join(clean)

    # 🧼 Normalize spacing (convert multiple dashes/underscores/spaces)
    result = re.sub(r'[ \-_]+', ' ', result)

    return result.strip()


# ✅ Clean rename function with junk filter
async def rename_file(file, sender, caption=None):
    delete_words = load_delete_words(sender)
    replacements = load_replacement_words(sender)
    custom_rename_tag = get_user_rename_preference(sender)

    # Separate directory and filename
    directory = os.path.dirname(file)
    filename = os.path.basename(file)
    base_name, ext = os.path.splitext(filename)
    
    ext = ext if ext and len(ext) <= 6 else ".mp4"
    original_base = base_name

    # Use caption if filename is empty/generic
    if not original_base.strip() or original_base.lower() in ['untitled', 'noname', 'video', 'image']:
        if caption:
            # Take first 50 words of caption as filename
            words = caption.split()[:50]
            base_name = ' '.join(words)
        else:
            # Fallback to timestamp if no caption
            base_name = f"file_{int(time.time())}"
    else:
        base_name = original_base

    # Clean the base name
    base_name = os.path.basename(base_name)

    # Apply advanced cleaning
    base_name = clean_text_advanced(base_name, sender)
    for word in delete_words:
        base_name = base_name.replace(word, "")  # Remove banned words
    for word, replace_word in replacements.items():
        base_name = base_name.replace(word, replace_word)  # Apply word replacements

    # Clean Unicode while preserving spaces and basic punctuation
    base_name = strip_unicode_junk(base_name)

    # Final filename assembly
    new_filename = f"{base_name.strip()} {custom_rename_tag}{ext}".strip()
    
    # Ensure filename isn't empty after processing
    if not os.path.splitext(new_filename)[0]:
        new_filename = f"document_{int(time.time())}{ext}"

    new_file_path = os.path.join(directory, new_filename)

    # Perform the rename
    await asyncio.to_thread(os.rename, file, new_file_path)
    return new_file_path


def progress_callback(done, total, user_id):
    # Check if this user already has progress tracking
    if user_id not in user_progress:
        user_progress[user_id] = {
            'previous_done': 0,
            'previous_time': time.time()
        }
    
    # Retrieve the user's tracking data
    user_data = user_progress[user_id]
    
    # Calculate the percentage of progress
    percent = (done / total) * 100
    
    # Format the progress bar
    completed_blocks = int(percent // 10)
    remaining_blocks = 10 - completed_blocks
    progress_bar = "♦" * completed_blocks + "◇" * remaining_blocks
    
    # Convert done and total to MB for easier reading
    done_mb = done / (1024 * 1024)  # Convert bytes to MB
    total_mb = total / (1024 * 1024)
    
    # Calculate the upload speed (in bytes per second)
    speed = done - user_data['previous_done']
    elapsed_time = time.time() - user_data['previous_time']
    
    if elapsed_time > 0:
        speed_bps = speed / elapsed_time  # Speed in bytes per second
        speed_mbps = (speed_bps * 8) / (1024 * 1024)  # Speed in Mbps
    else:
        speed_mbps = 0
    
    # Estimated time remaining (in seconds)
    if speed_bps > 0:
        remaining_time = (total - done) / speed_bps
    else:
        remaining_time = 0
    
    # Convert remaining time to minutes
    remaining_time_min = remaining_time / 60
    
    # Format the final output as needed
    final = (
        f"╭──────────────────╮\n"
        f"│     **__II_LevelUP_II ⚡ Uploader__**       \n"
        f"├──────────\n"
        f"│ {progress_bar}\n\n"
        f"│ **__Progress:__** {percent:.2f}%\n"
        f"│ **__Done:__** {done_mb:.2f} MB / {total_mb:.2f} MB\n"
        f"│ **__Speed:__** {speed_mbps:.2f} Mbps\n"
        f"│ **__ETA:__** {remaining_time_min:.2f} min\n"
        f"╰──────────────────╯\n\n"
        f"**__Pwrd by CHOSEN ONE ⚝__**"
    )
    
    # Update tracking variables for the user
    user_data['previous_done'] = done
    user_data['previous_time'] = time.time()
    
    return final


def dl_progress_callback(done, total, user_id):
    # Check if this user already has progress tracking
    if user_id not in user_progress:
        user_progress[user_id] = {
            'previous_done': 0,
            'previous_time': time.time()
        }
    
    # Retrieve the user's tracking data
    user_data = user_progress[user_id]
    
    # Calculate the percentage of progress
    percent = (done / total) * 100
    
    # Format the progress bar
    completed_blocks = int(percent // 10)
    remaining_blocks = 10 - completed_blocks
    progress_bar = "♦" * completed_blocks + "◇" * remaining_blocks
    
    # Convert done and total to MB for easier reading
    done_mb = done / (1024 * 1024)  # Convert bytes to MB
    total_mb = total / (1024 * 1024)
    
    # Calculate the upload speed (in bytes per second)
    speed = done - user_data['previous_done']
    elapsed_time = time.time() - user_data['previous_time']
    
    if elapsed_time > 0:
        speed_bps = speed / elapsed_time  # Speed in bytes per second
        speed_mbps = (speed_bps * 8) / (1024 * 1024)  # Speed in Mbps
    else:
        speed_mbps = 0
    
    # Estimated time remaining (in seconds)
    if speed_bps > 0:
        remaining_time = (total - done) / speed_bps
    else:
        remaining_time = 0
    
    # Convert remaining time to minutes
    remaining_time_min = remaining_time / 60
    
    # Format the final output as needed
    final = (
        f"╭──────────────────╮\n"
        f"│     **__II_LevelUP_II ⚡ Downloader__**       \n"
        f"├──────────\n"
        f"│ {progress_bar}\n\n"
        f"│ **__Progress:__** {percent:.2f}%\n"
        f"│ **__Done:__** {done_mb:.2f} MB / {total_mb:.2f} MB\n"
        f"│ **__Speed:__** {speed_mbps:.2f} Mbps\n"
        f"│ **__ETA:__** {remaining_time_min:.2f} min\n"
        f"╰──────────────────╯\n\n"
        f"**__Pwrd by CHOSEN ONE ⚝__**"
    )
    
    # Update tracking variables for the user
    user_data['previous_done'] = done
    user_data['previous_time'] = time.time()
    
    return final

# split function .... ?( to handle gareeb bot coder jo string n lga paaye)

async def split_and_upload_file(app, sender, target_chat_id, file_path, caption, topic_id):
    if not os.path.exists(file_path):
        await app.send_message(sender, "❌ File not found!")
        return

    file_size = os.path.getsize(file_path)
    start = await app.send_message(sender, f"ℹ️ File size: {file_size / (1024 * 1024):.2f} MB")
    PART_SIZE =  1.9 * 1024 * 1024 * 1024

    part_number = 0
    with open(file_path, "rb") as f:
        while True:
            # Create part filename
            base_name, file_ext = os.path.splitext(file_path)
            part_file = f"{base_name}.part{str(part_number).zfill(3)}{file_ext}"
            
            # Read and write chunks until part is complete
            with open(part_file, "wb") as part_f:
                bytes_written = 0
                while bytes_written < PART_SIZE:
                    chunk = f.read(min(1024 * 1024, int(PART_SIZE - bytes_written))) # 1MB chunks
                    if not chunk:
                        break
                    part_f.write(chunk)
                    bytes_written += len(chunk)
            
            if os.path.getsize(part_file) == 0:
                os.remove(part_file)
                break


            # Uploading part
            edit = await app.send_message(target_chat_id, f"⬆️ Uploading part {part_number + 1}...")
            part_caption = f"{caption} \n\n**Part : {part_number + 1}**"
            await app.send_document(target_chat_id, document=part_file, caption=part_caption, reply_to_message_id=topic_id,
                progress=progress_bar,
                progress_args=("╭─────────────────────╮\n│      **__Pyro Uploader__**\n├─────────────────────", edit, time.time())
            )
            await edit.delete()
            os.remove(part_file)  # Cleanup after upload

            part_number += 1

    await start.delete()
    os.remove(file_path)
