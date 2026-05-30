import os
import threading
from flask import Flask

# --- FLASK SERVER SETUP FOR RENDER (ADDED BY MINOX AUTO SETUP) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is successfully running on Render!"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

import telebot
import os
import subprocess
import sys
import json
import datetime
import zipfile
import shutil
import random
import string
from telebot import types
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# সার্ভার স্ট্যাটাস ফেচ করার চেষ্টা
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# ক্রেডেনশিয়ালস
API_TOKEN = '8935988605:AAHqBnPHZkQv1HyAltb_H_MdsUfxaZ8w9KU'
SUPERADMIN_ID = 5409553122  # প্রধান সুপারঅ্যাডমিন আইডি

# threaded=False ব্যবহারের মাধ্যমে শেয়ার্ড হোস্টিংয়ের থ্রেড এরর সমাধান করা হয়েছে
bot = telebot.TeleBot(API_TOKEN, threaded=False)

# ডাটাবেস এবং ডিরেক্টরি সেটআপ
DB_FILE = "users_db.json"
os.makedirs("hosted_bots", exist_ok=True)

# রানিং বটের প্রসেস ট্র্যাকার
running_bots = {}
user_states = {}       # {user_id: state}
active_deposits = {}   # {user_id: {method, amount, sender_acc, txid, photo_id}}

# পেমেন্ট মেথড ডিটেইলস (ডিফল্ট)
PAYMENT_DETAILS = {
    "bKash": "01706490391 (Personal Send Money)",
    "Rocket": "01706490391 (Personal Send Money)",
    "Nagad": "01706490391 (Personal Send Money)",
    "Binance": "Pay ID: 880516152"
}

# --- প্রিমিয়াম কাস্টম ইমোজি ম্যাপ ---
EMOJIS = {
    "python": ("5226717982230591144", "💻"),
    "launching": ("6131845772511024828", "🚀"),
    "extracting": ("5262839322909891684", "📦"),
    "buy": ("5350679208068667881", "🛒"),
    "free": ("6237544939140421335", "🆓"),
    "done": ("6235415550189643150", "✅"),
    "wrong": ("5210952531676504517", "❌"),
    "wallet": ("6053003027793578665", "💳"),
    "products": ("6237615509748061371", "🛍️"),
    "money": ("6233367447789899509", "💰"),
    "admin_panel": ("5258096772776991776", "⚙️"),
    "admin": ("5260553279321944543", "👑"),
    "add": ("5397916757333654639", "➕"),
    "process": ("5370715282044100355", "⏳"),
    "stop": ("5956074558044770726", "🛑"),
    "nagad": ("5352985330628730418", "🔴"),
    "rocket": ("5346042941196507141", "🟣"),
    "binance": ("5348212415077064131", "🟡"),
    "bkash": ("5348469219761626211", "💖"),
    "time": ("5787488119490088755", "⏰"),
    "lock": ("5445267414562389170", "🔒"),
    "delete": ("5019523190800450125", "🗑️"),
    "deploy_btn": ("5861665979968262792", "✅"),
    "broadcast": ("6131678986046018775", "📢"),
    "status_btn": ("5352877703043258544", "🟡"),
    "warning": ("5855178350263276469", "⚠️"),
    "bot": ("5864127571754489150", "🤖"),
    "file": ("5352721946054268944", "📄"),
    "support": ("5334763399299506604", "📞"),
    "user": ("5314725350920409848", "👤"),
    "search": ("5019523190800450125", "🔍"),
    "stats": ("5258096772776991776", "📊"),
    "gift": ("5397916757333654639", "🎁"),
    "back": ("5210952531676504517", "🔙")
}

def get_emj(key):
    eid, fallback = EMOJIS.get(key, ("", ""))
    if eid:
        return f'<tg-emoji emoji-id="{eid}">{fallback}</tg-emoji>'
    return fallback

def get_emj_id(key):
    return EMOJIS.get(key, ("", ""))[0]

# ==================================================
# --- STYLE PATCH FOR TELEBOT BUTTONS (COLOR PATCH) ---
# ==================================================
def safe_int_emoji_id(val):
    if not val:
        return None
    try:
        val_str = str(val).strip()
        if val_str.isdigit():
            return int(val_str)
    except:
        pass
    return None

_old_inline_dict = InlineKeyboardButton.to_dict
def _new_inline_dict(self):
    d = _old_inline_dict(self)
    if hasattr(self, 'style'): d['style'] = self.style
    if hasattr(self, 'icon_custom_emoji_id') and self.icon_custom_emoji_id:
        val = safe_int_emoji_id(self.icon_custom_emoji_id)
        if val is not None:
            d['icon_custom_emoji_id'] = val
    return d
InlineKeyboardButton.to_dict = _new_inline_dict

_old_kb_dict = KeyboardButton.to_dict
def _new_kb_dict(self):
    d = _old_kb_dict(self)
    if hasattr(self, 'style'): d['style'] = self.style
    if hasattr(self, 'icon_custom_emoji_id') and self.icon_custom_emoji_id:
        val = safe_int_emoji_id(self.icon_custom_emoji_id)
        if val is not None:
            d['icon_custom_emoji_id'] = val
    return d
KeyboardButton.to_dict = _new_kb_dict

def ibtn(text, callback_data=None, url=None, style=None, custom_emoji_id=None):
    kwargs = {'text': text}
    if callback_data: kwargs['callback_data'] = callback_data
    if url: kwargs['url'] = url
    
    emoji_val = safe_int_emoji_id(custom_emoji_id)
    if emoji_val is not None:
        kwargs['icon_custom_emoji_id'] = emoji_val
            
    b = InlineKeyboardButton(**kwargs)
    if style: b.style = style
    if emoji_val is not None: b.icon_custom_emoji_id = emoji_val
    return b

def rbtn(text, style=None, custom_emoji_id=None):
    b = KeyboardButton(text=text)
    if style: b.style = style
    emoji_val = safe_int_emoji_id(custom_emoji_id)
    if emoji_val is not None: b.icon_custom_emoji_id = emoji_val
    return b

# --- ডাটাবেস ফাংশনসমূহ ---
def load_db():
    default_db = {
        "revenue": 0.0,
        "maintenance": False,
        "banned_users": [],
        "users": {},
        "promo_codes": {},
        "tx_logs": [],
        "admins": [SUPERADMIN_ID],
        "settings": {
            "default_slot_limit": 2,
            "trial_days": 1,
            "payment_bkash": "01706490391 (Personal Send Money)",
            "payment_rocket": "01706490391 (Personal Send Money)",
            "payment_nagad": "01706490391 (Personal Send Money)",
            "payment_binance": "Pay ID: 880516152"
        },
        "plans": {
            "1": {"name": "Trial VPS", "cost": 0, "days": 1},
            "7": {"name": "7 Days VPS", "cost": 49, "days": 7},
            "15": {"name": "15 Days VPS", "cost": 89, "days": 15},
            "30": {"name": "30 Days VPS", "cost": 149, "days": 30}
        }
    }
    
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return default_db
                
                # লেগ্যাসি ডাটাবেজ ফিক্সিং
                if "users" not in data:
                    data = {"users": data}
                    
                data.setdefault("revenue", 0.0)
                data.setdefault("maintenance", False)
                data.setdefault("banned_users", [])
                data.setdefault("users", {})
                data.setdefault("promo_codes", {})
                data.setdefault("tx_logs", [])
                data.setdefault("admins", [SUPERADMIN_ID])
                
                # গ্লোবাল সেটিংস অবজেক্ট রিকোভারি ও ডাইনামিক মার্জ
                settings = data.setdefault("settings", default_db["settings"])
                for k, v in default_db["settings"].items():
                    settings.setdefault(k, v)
                    
                # প্যাকেজ কন্ট্রোলার রিকোভারি
                data.setdefault("plans", default_db["plans"])
                
                return data
        except:
            return default_db
    return default_db

def save_db(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=4)

# মাল্টি-অ্যাডমিন অথরাইজেশন চেক
def is_admin(user_id, db=None):
    if user_id == SUPERADMIN_ID:
        return True
    if not db:
        db = load_db()
    db_admins = db.setdefault("admins", [SUPERADMIN_ID])
    return user_id in db_admins or str(user_id) in db_admins

def get_user(user_id, db, username=None):
    uid = str(user_id)
    if uid not in db["users"]:
        db["users"][uid] = {
            "balance": 0.0,
            "plan": "NONE",
            "plan_expiry": None,
            "free_claimed": False,
            "slot_limit": db.get("settings", {}).get("default_slot_limit", 2),
            "username": username or "N/A"
        }
    else:
        if username:
            db["users"][uid]["username"] = username
    return db["users"][uid]

def is_plan_active(user_id, db):
    if is_admin(user_id, db):
        return True
    user = get_user(user_id, db)
    if user["plan"] == "NONE" or not user["plan_expiry"]:
        return False
    try:
        expiry = datetime.datetime.strptime(user["plan_expiry"], "%Y-%m-%d %H:%M:%S")
        if datetime.datetime.now() < expiry:
            return True
    except:
        return False
    return False

def check_and_stop_expired_bot(user_id, db):
    if is_admin(user_id, db):
        return
    if not is_plan_active(user_id, db):
        user = get_user(user_id, db)
        limit = user.get("slot_limit", 2)
        for i in range(1, limit + 1):
            slot_name = f"slot{i}"
            stop_bot_process(user_id, slot_name)
        if user["plan"] != "NONE":
            user["plan"] = "NONE"
            user["plan_expiry"] = None
            save_db(db)
            bot.send_message(user_id, f"{get_emj('wrong')} Your subscription plan has expired! Your running bots have been stopped.", parse_mode="HTML")

# --- সিকিউরিটি চেক মিডলওয়্যার ---
def check_security(message):
    db = load_db()
    user_id = message.from_user.id
    if str(user_id) in db.get("banned_users", []):
        bot.send_message(message.chat.id, f"{get_emj('wrong')} <b>Access Denied</b>\n\nYour account has been banned from this platform.", parse_mode="HTML")
        return True
    if db.get("maintenance", False) and not is_admin(user_id, db):
        bot.send_message(message.chat.id, f"{get_emj('warning')} <b>System Maintenance</b>\n\nThe platform is currently undergoing scheduled maintenance. Please try again later.", parse_mode="HTML")
        return True
    return False

# --- প্রসেস কন্ট্রোল ---
def get_bot_status(user_id, slot):
    if user_id in running_bots and slot in running_bots[user_id]:
        process = running_bots[user_id][slot]
        if process and process.poll() is None:
            return "RUNNING"
    return "STOPPED"

def stop_bot_process(user_id, slot):
    if user_id in running_bots and slot in running_bots[user_id]:
        process = running_bots[user_id][slot]
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=3)
            except:
                process.kill()
        running_bots[user_id][slot] = None
        return True
    return False

def find_entrypoint(slot_dir):
    possible_entrypoints = ["main.py", "bot.py", "index.py"]
    for filename in possible_entrypoints:
        if os.path.exists(os.path.join(slot_dir, filename)):
            return os.path.join(slot_dir, filename)
    if os.path.exists(slot_dir):
        py_files = [f for f in os.listdir(slot_dir) if f.endswith('.py')]
        if py_files:
            return os.path.join(slot_dir, py_files[0])
    return None

def start_bot_process(user_id, slot):
    user_dir = f"hosted_bots/{user_id}/{slot}"
    entrypoint = find_entrypoint(user_dir)
    if not entrypoint:
        return False, "No entrypoint python file (e.g. main.py or bot.py) was found."
    
    log_path = f"{user_dir}/bot.log"
    stop_bot_process(user_id, slot)
    
    log_file = open(log_path, 'a')
    log_file.write(f"\n--- Bot Started at {datetime.datetime.now()} ---\n")
    log_file.flush()
    
    process = subprocess.Popen([sys.executable, entrypoint], stdout=log_file, stderr=subprocess.STDOUT)
    
    if user_id not in running_bots:
        running_bots[user_id] = {}
    running_bots[user_id][slot] = process
    return True, os.path.basename(entrypoint)

# --- কীবোর্ড বাটন ---
def get_main_keyboard(user_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = rbtn("Deploy Bot", style="primary", custom_emoji_id=get_emj_id("deploy_btn"))
    btn2 = rbtn("Status & Manage", style="success", custom_emoji_id=get_emj_id("status_btn"))
    btn3 = rbtn("Products / Plans", style="success", custom_emoji_id=get_emj_id("products"))
    btn4 = rbtn("Deposit & Wallet", style="primary", custom_emoji_id=get_emj_id("wallet"))
    btn5 = rbtn("Support", style="primary", custom_emoji_id=get_emj_id("support"))
    
    markup.add(btn1, btn2)
    markup.add(btn3, btn4)
    markup.add(btn5)
    
    if is_admin(user_id):
        btn_admin = rbtn("Admin Panel", style="danger", custom_emoji_id=get_emj_id("admin"))
        markup.add(btn_admin)
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if check_security(message): return
    
    user_id = message.from_user.id
    db = load_db()
    
    uid_str = str(user_id)
    is_new = uid_str not in db["users"]
    
    get_user(user_id, db, message.from_user.username)
    save_db(db)
    
    user_states[user_id] = None
    active_deposits.pop(user_id, None)
    
    if is_new:
        alert_text = (
            f"{get_emj('add')} <b>First-Time User Joined!</b>\n\n"
            f"{get_emj('user')} <b>Name:</b> {message.from_user.first_name}\n"
            f"{get_emj('warning')} <b>User ID:</b> <code>{user_id}</code>\n"
            f"{get_emj('admin')} <b>Total Users Now:</b> <code>{len(db['users'])}</code>"
        )
        try:
            bot.send_message(SUPERADMIN_ID, alert_text, parse_mode="HTML")
        except:
            pass
    
    welcome_text = (
        f"{get_emj('bot')} <b>Welcome to the Premium Python Bot Hosting Platform!</b>\n\n"
        f"Here you can host up to 2 Python bots in separate slots. "
        f"Please purchase a subscription plan from <b>Products / Plans</b> to get started."
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_keyboard(user_id), parse_mode="HTML")

# --- সাপোর্ট পেজ হ্যান্ডলার ---
@bot.message_handler(func=lambda message: message.text is not None and "Support" in message.text)
def show_support_info(message):
    if check_security(message): return
    
    text = (
        f"{get_emj('support')} <b>Customer Support</b>\n\n"
        f"If you have any questions, encounter issues, or need custom slot configurations, "
        f"please click the button below to contact our support agent."
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(ibtn("Contact Support", url="https://t.me/rahi455", style="success", custom_emoji_id=get_emj_id("support")))
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

# --- স্লট সিলেক্ট ---
@bot.message_handler(func=lambda message: message.text is not None and "Deploy Bot" in message.text)
def deploy_slot_select(message):
    if check_security(message): return
    
    user_id = message.from_user.id
    db = load_db()
    check_and_stop_expired_bot(user_id, db)
    
    if not is_plan_active(user_id, db):
        bot.send_message(
            message.chat.id, 
            f"{get_emj('wrong')} Sorry! You do not have an active subscription plan. Please buy a plan from <b>Products / Plans</b> first.",
            parse_mode="HTML"
        )
        return

    user_data = get_user(user_id, db, message.from_user.username)
    limit = user_data.get("slot_limit", 2)

    markup = InlineKeyboardMarkup(row_width=2)
    buttons = []
    for i in range(1, limit + 1):
        slot_name = f"slot{i}"
        s_status = get_bot_status(user_id, slot_name)
        s_label = "Active" if s_status == "RUNNING" else "Free"
        buttons.append(ibtn(f"Slot {i} ({s_label})", callback_data=f"select_slot_deploy_{slot_name}", style="primary", custom_emoji_id=get_emj_id("time" if s_status == "RUNNING" else "free")))
        
    markup.add(*buttons)
    
    bot.send_message(
        message.chat.id, 
        f"{get_emj('admin_panel')} <b>Please select your deployment slot:</b>\n"
        f"<i>(Deploying on an active slot will overwrite previous files)</i>", 
        reply_markup=markup, 
        parse_mode="HTML"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("select_slot_deploy_"))
def process_slot_deploy_selection(call):
    user_id = call.from_user.id
    slot = call.data.replace("select_slot_deploy_", "")
    
    user_states[user_id] = f"waiting_for_zip_{slot}"
    bot.answer_callback_query(call.id)
    
    prompt_msg = (
        f"{get_emj('file')} You have selected <b>{slot.upper()}</b>.\n\n"
        f"Please send your project's <b>ZIP (.zip) file</b>.\n\n"
        f"{get_emj('process')} <b>Rules:</b>\n"
        f"[•] The ZIP file must contain a main running file named either <code>main.py</code> or <code>bot.py</code> in the root directory.\n"
        f"[•] If your project has external dependencies, include a <code>requirements.txt</code> file in the root directory."
    )
    bot.send_message(call.message.chat.id, prompt_msg, parse_mode="HTML")

# জিপ রিসিভার হ্যান্ডলার
@bot.message_handler(content_types=['document'], func=lambda message: user_states.get(message.from_user.id) is not None and user_states[message.from_user.id].startswith("waiting_for_zip_"))
def handle_zip_deployment(message):
    user_id = message.from_user.id
    slot = user_states[user_id].replace("waiting_for_zip_", "")
    user_states[user_id] = None
    db = load_db()
    
    if not is_plan_active(user_id, db):
        bot.send_message(message.chat.id, f"{get_emj('wrong')} You do not have an active subscription plan.", parse_mode="HTML")
        return
        
    if not message.document.file_name.endswith('.zip'):
        bot.send_message(message.chat.id, f"{get_emj('wrong')} Invalid file format! Please upload only ZIP (.zip) files.", parse_mode="HTML")
        return

    status_msg = bot.send_message(message.chat.id, f"{get_emj('process')} Uploading file to {slot.upper()}...", parse_mode="HTML")

    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        slot_dir = f"hosted_bots/{user_id}/{slot}"
        
        if os.path.exists(slot_dir):
            shutil.rmtree(slot_dir)
        os.makedirs(slot_dir, exist_ok=True)
        
        zip_path = f"{slot_dir}/bot_archive.zip"
        log_path = f"{slot_dir}/bot.log"
        
        with open(zip_path, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        bot.edit_message_text(f"{get_emj('extracting')} Extracting ZIP file...", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(slot_dir)
            
        os.remove(zip_path)
            
        stop_bot_process(user_id, slot)

        log_file = open(log_path, 'w')
        
        # requirements.txt হ্যান্ডলিং
        req_path = f"{slot_dir}/requirements.txt"
        if os.path.exists(req_path):
            bot.edit_message_text(f"{get_emj('process')} requirements.txt found! Installing modules online (This may take a moment)...", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")
            log_file.write("--- Installing requirements.txt ---\n")
            log_file.flush()
            
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", req_path], 
                stdout=log_file, 
                stderr=subprocess.STDOUT
            )
            log_file.write("\n--- Finished Installing Requirements ---\n\n")
            log_file.flush()

        bot.edit_message_text(f"{get_emj('launching')} Launching your bot...", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")
        log_file.close()
        
        success, res = start_bot_process(user_id, slot)
        if success:
            bot.edit_message_text(f"{get_emj('done')} <b>{slot.upper()}</b> has been successfully deployed and started!\n\n{get_emj('launching')} Running entrypoint: <code>{res}</code>", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")
        else:
            bot.edit_message_text(f"{get_emj('wrong')} Failed to run: {res}", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")
            
    except Exception as e:
        bot.send_message(message.chat.id, f"{get_emj('wrong')} An error occurred during deployment: {str(e)}", parse_mode="HTML")

# --- স্ট্যাটাস এবং ম্যানেজমেন্ট সেকশন ---
@bot.message_handler(func=lambda message: message.text is not None and "Status & Manage" in message.text)
def show_status(message):
    if check_security(message): return
    
    user_id = message.from_user.id
    db = load_db()
    check_and_stop_expired_bot(user_id, db)
    
    user_data = get_user(user_id, db, message.from_user.username)
    limit = user_data.get("slot_limit", 2)
    
    status_text = f"{get_emj('status_btn')} <b>Your Deployment Slots Status:</b>\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for i in range(1, limit + 1):
        slot_name = f"slot{i}"
        s_status = get_bot_status(user_id, slot_name)
        s_icon = f"{get_emj('done')} RUNNING" if s_status == "RUNNING" else f"{get_emj('stop')} STOPPED"
        s_has_file = os.path.exists(f"hosted_bots/{user_id}/{slot_name}")
        s_file_status = f"{get_emj('file')} Files exist" if s_has_file else f"{get_emj('wrong')} No files"
        
        status_text += f"{get_emj('status_btn')} <b>Slot {i} Status:</b> {s_icon}\n{get_emj('file')} Project Directory: {s_file_status}\n\n"
        if s_has_file:
            markup.add(ibtn(f"Manage Slot {i}", callback_data=f"manage_slot_{slot_name}", style="primary", custom_emoji_id=get_emj_id("admin_panel")))
        
    status_text += "Use the buttons below to control your bots:"
    bot.send_message(message.chat.id, status_text, reply_markup=markup, parse_mode="HTML")

# স্লট কন্ট্রোল প্যানেল
@bot.callback_query_handler(func=lambda call: call.data.startswith("manage_slot_"))
def manage_slot_panel(call):
    user_id = call.from_user.id
    slot = call.data.replace("manage_slot_", "")
    
    status = get_bot_status(user_id, slot)
    status_text = f"{get_emj('done')} RUNNING" if status == "RUNNING" else f"{get_emj('stop')} STOPPED"
    
    control_text = (
        f"{get_emj('admin_panel')} <b>{slot.upper()} Control Panel</b>\n\n"
        f"{get_emj('stats')} Current Status: <b>{status_text}</b>\n\n"
        f"Perform actions below:"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    if status == "RUNNING":
        btn_stop = ibtn("Stop Bot", callback_data=f"act_{slot}_stop", style="danger", custom_emoji_id=get_emj_id("stop"))
        btn_restart = ibtn("Restart", callback_data=f"act_{slot}_restart", style="primary", custom_emoji_id=get_emj_id("process"))
        markup.add(btn_stop, btn_restart)
    else:
        btn_start = ibtn("Start Bot", callback_data=f"act_{slot}_start", style="success", custom_emoji_id=get_emj_id("launching"))
        markup.add(btn_start)
        
    btn_logs = ibtn("View Logs", callback_data=f"act_{slot}_logs", style="primary", custom_emoji_id=get_emj_id("python"))
    btn_backup = ibtn("Download Backup", callback_data=f"act_{slot}_backup", style="primary", custom_emoji_id=get_emj_id("extracting"))
    btn_delete = ibtn("Reset Slot (Delete)", callback_data=f"act_{slot}_delete", style="danger", custom_emoji_id=get_emj_id("delete"))
    btn_back = ibtn("Back to Status", callback_data="back_to_status_view", style="danger", custom_emoji_id=get_emj_id("wrong"))
    
    markup.add(btn_logs, btn_backup)
    markup.add(btn_delete)
    markup.add(btn_back)
    
    bot.edit_message_text(control_text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="HTML")

# অ্যাকশন প্রসেসর
@bot.callback_query_handler(func=lambda call: call.data.startswith("act_"))
def process_slot_action(call):
    user_id = call.from_user.id
    parts = call.data.split("_")
    slot = parts[1]
    action = parts[2]
    
    bot.answer_callback_query(call.id)
    slot_dir = f"hosted_bots/{user_id}/{slot}"
    
    if action == "stop":
        stop_bot_process(user_id, slot)
        bot.send_message(call.message.chat.id, f"{get_emj('stop')} {slot.upper()} bot has been stopped.", parse_mode="HTML")
        
    elif action == "start":
        db = load_db()
        if not is_plan_active(user_id, db):
            bot.send_message(call.message.chat.id, f"{get_emj('wrong')} Your subscription plan is expired.", parse_mode="HTML")
            return
        success, res = start_bot_process(user_id, slot)
        if success:
            bot.send_message(call.message.chat.id, f"{get_emj('done')} {slot.upper()} bot successfully started! Entry file: <code>{res}</code>", parse_mode="HTML")
        else:
            bot.send_message(call.message.chat.id, f"{get_emj('wrong')} Failed to start: {res}", parse_mode="HTML")
            
    elif action == "restart":
        db = load_db()
        if not is_plan_active(user_id, db):
            bot.send_message(call.message.chat.id, f"{get_emj('wrong')} Your subscription plan is expired.", parse_mode="HTML")
            return
        stop_bot_process(user_id, slot)
        success, res = start_bot_process(user_id, slot)
        if success:
            bot.send_message(call.message.chat.id, f"{get_emj('process')} {slot.upper()} bot successfully restarted!", parse_mode="HTML")
        else:
            bot.send_message(call.message.chat.id, f"{get_emj('wrong')} Restart failed: {res}", parse_mode="HTML")
            
    elif action == "logs":
        log_path = f"{slot_dir}/bot.log"
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                logs = f.read()[-1000:]
            if not logs.strip():
                logs = "Logs are empty."
            bot.send_message(call.message.chat.id, f"📋 <b>{slot.upper()} Logs:</b>\n```\n{logs}\n```", parse_mode="Markdown")
        else:
            bot.send_message(call.message.chat.id, "No log file found.")
            
    elif action == "backup":
        if os.path.exists(slot_dir):
            backup_zip_path = f"hosted_bots/{user_id}/{slot}_backup"
            shutil.make_archive(backup_zip_path, 'zip', slot_dir)
            
            with open(f"{backup_zip_path}.zip", 'rb') as doc:
                bot.send_document(call.message.chat.id, doc, caption=f"{get_emj('extracting')} <b>{slot.upper()} Project Backup Archive</b>", parse_mode="HTML")
                
            os.remove(f"{backup_zip_path}.zip")
        else:
            bot.send_message(call.message.chat.id, "No project files found.")
            
    elif action == "delete":
        stop_bot_process(user_id, slot)
        if os.path.exists(slot_dir):
            shutil.rmtree(slot_dir)
        bot.send_message(call.message.chat.id, f"{get_emj('delete')} All files for {slot.upper()} have been deleted.", parse_mode="HTML")

# --- প্রোডাক্টস / ডাইনামিক সাবস্ক্রিপশন প্ল্যান্স ---
@bot.message_handler(func=lambda message: message.text is not None and "Products / Plans" in message.text)
def show_products_text(message):
    if check_security(message): return
    
    db = load_db()
    plans = db.get("plans", {})
    
    if not plans:
        bot.send_message(message.chat.id, f"{get_emj('wrong')} No packages are currently active.")
        return
        
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for pid, pinfo in plans.items():
        name = pinfo.get("name", "Plan")
        cost = pinfo.get("cost", 0)
        buttons.append(ibtn(f"{name} ({cost} Tk)", callback_data=f"buy_plan_{pid}_{cost}", style="primary", custom_emoji_id=get_emj_id("buy")))
        
    markup.add(*buttons)
    bot.send_message(message.chat.id, f"{get_emj('products')} <b>Please select your subscription plan:</b>", reply_markup=markup, parse_mode="HTML")

# --- ওয়ালেট এবং ডিপোজিট সিস্টেম ---
@bot.message_handler(func=lambda message: message.text is not None and "Deposit & Wallet" in message.text)
def show_wallet_text(message):
    if check_security(message): return
    
    user_id = message.from_user.id
    db = load_db()
    user = get_user(user_id, db, message.from_user.username)
    
    plan_info = user["plan"]
    expiry_info = user["plan_expiry"] if user["plan_expiry"] else "N/A"
    
    wallet_text = (
        f"{get_emj('wallet')} <b>Your Wallet Details:</b>\n\n"
        f"{get_emj('money')} Current Balance: <b>{user['balance']} Tk</b>\n"
        f"{get_emj('products')} Current Plan: <b>{plan_info}</b>\n"
        f"{get_emj('time')} Plan Expiry: <b>{expiry_info}</b>\n\n"
        f"To recharge your balance or redeem promo codes, use the buttons below."
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    deposit_btn = ibtn("Deposit Balance", callback_data="start_deposit", style="success", custom_emoji_id=get_emj_id("add"))
    promo_btn = ibtn("Redeem Promo Code", callback_data="user_promo_claim", style="primary", custom_emoji_id=get_emj_id("gift"))
    markup.add(deposit_btn, promo_btn)
    bot.send_message(message.chat.id, wallet_text, reply_markup=markup, parse_mode="HTML")

# --- কলব্যাক কোয়েরি হ্যান্ডলার (ডিপোজিট ও অন্যান্য সাধারণ ইউজার কুয়েরি) ---
@bot.callback_query_handler(func=lambda call: call.data == "start_deposit" or call.data.startswith("dep_method_") or call.data.startswith("buy_plan_") or call.data.startswith("adm_dep_") or call.data == "user_promo_claim")
def other_callback_handler(call):
    user_id = call.from_user.id
    db = load_db()
    user = get_user(user_id, db, call.from_user.username)
    
    bot.answer_callback_query(call.id)
    
    if call.data == "user_promo_claim":
        user_states[user_id] = "waiting_promo_code"
        bot.send_message(call.message.chat.id, f"{get_emj('gift')} Please enter or send your Promo Code:", parse_mode="HTML")
        return

    # ১. ডিপোজিট প্রসেস শুরু করা
    if call.data == "start_deposit":
        active_deposits[user_id] = {}
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn1 = ibtn("bKash", callback_data="dep_method_bKash", style="primary", custom_emoji_id=get_emj_id("bkash"))
        btn2 = ibtn("Rocket", callback_data="dep_method_Rocket", style="primary", custom_emoji_id=get_emj_id("rocket"))
        btn3 = ibtn("Nagad", callback_data="dep_method_Nagad", style="primary", custom_emoji_id=get_emj_id("nagad"))
        btn4 = ibtn("Binance", callback_data="dep_method_Binance", style="primary", custom_emoji_id=get_emj_id("binance"))
        markup.add(btn1, btn2, btn3, btn4)
        
        bot.edit_message_text(f"{get_emj('wallet')} <b>Please select your payment method:</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # ২. পেমেন্ট মেথড সিলেক্ট করা
    elif call.data.startswith("dep_method_"):
        method = call.data.split("_")[2]
        active_deposits[user_id] = {"method": method}
        
        settings = db.get("settings", {})
        details = ""
        if method == "bKash": details = settings.get("payment_bkash", PAYMENT_DETAILS["bKash"])
        elif method == "Nagad": details = settings.get("payment_nagad", PAYMENT_DETAILS["Nagad"])
        elif method == "Rocket": details = settings.get("payment_rocket", PAYMENT_DETAILS["Rocket"])
        elif method == "Binance": details = settings.get("payment_binance", PAYMENT_DETAILS["Binance"])
        
        bot.send_message(
            call.message.chat.id, 
            f"{get_emj('wallet')} <b>Payment Details:</b>\n[•] <code>{details}</code>\n\n"
            f"After sending money, please type and send the <b>Amount</b> you sent:",
            parse_mode="HTML"
        )
        user_states[user_id] = "dep_waiting_amount"

    # ৩. ডাইনামিক প্ল্যান ক্রয় প্রসেসিং (রেভিনিউ সংযোজন এবং অ্যাডমিন নোটিফিকেশন অ্যালার্ট)
    elif call.data.startswith("buy_plan_"):
        parts = call.data.split("_")
        plan_id = parts[2]
        
        plans = db.get("plans", {})
        if plan_id not in plans:
            bot.send_message(call.message.chat.id, f"{get_emj('wrong')} This plan is no longer available.")
            return
            
        pinfo = plans[plan_id]
        cost = float(pinfo.get("cost", 0))
        days = int(pinfo.get("days", 1))
        plan_name = pinfo.get("name", "Plan")
        
        if cost == 0:
            if user["free_claimed"] and not is_admin(user_id, db):
                bot.send_message(call.message.chat.id, f"{get_emj('wrong')} You have already claimed the free trial plan once.", parse_mode="HTML")
                return

        if user["balance"] >= cost or is_admin(user_id, db):
            if not is_admin(user_id, db):
                user["balance"] -= cost
                db["revenue"] = db.get("revenue", 0.0) + cost
            
            expiry_date = datetime.datetime.now() + datetime.timedelta(days=days)
            expiry_str = expiry_date.strftime("%Y-%m-%d %H:%M:%S")
            
            user["plan"] = plan_name
            user["plan_expiry"] = expiry_str
            if cost == 0:
                user["free_claimed"] = True
                
            # লগ ডাটাবেজে ট্রানজেকশন সেভ
            db.setdefault("tx_logs", []).append({
                "user_id": str(user_id),
                "type": "PLAN_PURCHASE",
                "amount": float(cost),
                "detail": plan_name,
                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            save_db(db)
            
            # প্ল্যান ক্রয় করলে অ্যাডমিনকে নোটিফিকেশন অ্যালার্ট পাঠানো
            purchase_alert = (
                f"{get_emj('money')} <b>New Plan Purchase Alert!</b>\n\n"
                f"👤 <b>User:</b> {call.from_user.first_name} (ID: <code>{user_id}</code>)\n"
                f"{get_emj('products')} <b>Plan:</b> <b>{plan_name}</b>\n"
                f"{get_emj('money')} <b>Cost:</b> <code>{cost} Tk</code>\n"
                f"{get_emj('time')} <b>Expiry:</b> <code>{expiry_str}</code>\n\n"
                f"💸 <b>Total Revenue:</b> <code>{db['revenue']} Tk</code>"
            )
            try:
                bot.send_message(SUPERADMIN_ID, purchase_alert, parse_mode="HTML")
            except:
                pass

            bot.send_message(call.message.chat.id, f"{get_emj('done')} <b>Success!</b> You have successfully purchased the <b>{plan_name}</b>.\nExpiry Date: {expiry_str}", parse_mode="HTML")
        else:
            bot.send_message(call.message.chat.id, f"{get_emj('wrong')} <b>Insufficient Balance!</b> This plan costs {cost} Tk. Please recharge your wallet first.", parse_mode="HTML")

    # ৪. পেমেন্ট অ্যাপ্রুভ / রিজেক্ট
    elif call.data.startswith("adm_dep_"):
        action = call.data.split("_")[2]
        target_id = call.data.split("_")[3]
        
        if action == "approve":
            amount = float(call.data.split("_")[4])
            target_user_data = get_user(target_id, db)
            target_user_data["balance"] += amount
            
            db.setdefault("tx_logs", []).append({
                "user_id": str(target_id),
                "type": "DEPOSIT",
                "amount": amount,
                "detail": "Admin Approved",
                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            save_db(db)
            
            bot.send_message(target_id, f"{get_emj('done')} <b>Success!</b> Your deposit of {amount} Tk has been approved and added to your balance.", parse_mode="HTML")
            bot.edit_message_caption(f"✅ Deposit Approved! User ID: `{target_id}` ({amount} Tk added).", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")
        
        elif action == "reject":
            bot.send_message(target_id, f"{get_emj('wrong')} <b>Rejected!</b> Your deposit request was rejected by admin. Please try again with valid information.", parse_mode="HTML")
            bot.edit_message_caption(f"❌ Deposit Request Rejected. User ID: `{target_id}`", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")

# ---  মাল্টি-স্টেপ প্রসেস হ্যান্ডলার ---
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) in ["dep_waiting_amount", "dep_waiting_sender", "dep_waiting_txid", "waiting_promo_code"])
def handle_deposit_steps(message):
    user_id = message.from_user.id
    state = user_states[user_id]
    
    if state == "waiting_promo_code":
        code_input = message.text.strip().upper()
        db = load_db()
        promos = db.get("promo_codes", {})
        user_states[user_id] = None
        
        if code_input not in promos:
            bot.send_message(message.chat.id, f"{get_emj('wrong')} Invalid Promo Code!", parse_mode="HTML")
            return
            
        promo = promos[code_input]
        
        # PROMO EXPIRY CHECK (মাল্টি-স্টেপ প্রোমো ফিক্সড)
        expiry_str = promo.get("expiry")
        if expiry_str:
            try:
                expiry = datetime.datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
                if datetime.datetime.now() > expiry:
                    bot.send_message(message.chat.id, f"{get_emj('wrong')} This promo code has expired!", parse_mode="HTML")
                    return
            except:
                pass
                
        used_by = promo.setdefault("used_by", [])
        
        if str(user_id) in used_by:
            bot.send_message(message.chat.id, f"{get_emj('wrong')} You have already redeemed this promo code once!", parse_mode="HTML")
            return
            
        if len(used_by) >= promo.get("max_uses", 1):
            bot.send_message(message.chat.id, f"{get_emj('wrong')} Sorry, this promo code limit has been reached!", parse_mode="HTML")
            return
            
        amount = promo.get("amount", 0.0)
        user = get_user(user_id, db, message.from_user.username)
        user["balance"] += amount
        used_by.append(str(user_id))
        
        # ট্রানজেকশন সেভ
        db.setdefault("tx_logs", []).append({
            "user_id": str(user_id),
            "type": "PROMO_CLAIM",
            "amount": float(amount),
            "detail": f"Code: {code_input}",
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        save_db(db)
        
        bot.send_message(message.chat.id, f"{get_emj('done')} <b>Congratulations!</b> You have claimed {amount} Tk balance using promo code!", parse_mode="HTML")
        return

    if user_id not in active_deposits:
        user_states[user_id] = None
        bot.send_message(message.chat.id, f"{get_emj('wrong')} Session expired. Please try again.", parse_mode="HTML")
        return

    if state == "dep_waiting_amount":
        try:
            amount = float(message.text)
            if amount <= 0:
                bot.send_message(message.chat.id, f"{get_emj('wrong')} Please enter a valid positive number.", parse_mode="HTML")
                return
            active_deposits[user_id]["amount"] = amount
            bot.send_message(message.chat.id, f"{get_emj('process')} Please enter the Sender Account Number you used to send money:", parse_mode="HTML")
            user_states[user_id] = "dep_waiting_sender"
        except ValueError:
            bot.send_message(message.chat.id, f"{get_emj('wrong')} Please send only digits for the amount (e.g. 100).", parse_mode="HTML")

    elif state == "dep_waiting_sender":
        sender_acc = message.text.strip()
        if not sender_acc:
            bot.send_message(message.chat.id, f"{get_emj('wrong')} Invalid account number.", parse_mode="HTML")
            return
        active_deposits[user_id]["sender_acc"] = sender_acc
        bot.send_message(message.chat.id, f"{get_emj('process')} Now please enter the Transaction ID (TxID):", parse_mode="HTML")
        user_states[user_id] = "dep_waiting_txid"

    elif state == "dep_waiting_txid":
        txid = message.text.strip()
        if not txid:
            bot.send_message(message.chat.id, f"{get_emj('wrong')} Invalid Transaction ID.", parse_mode="HTML")
            return
        active_deposits[user_id]["txid"] = txid
        bot.send_message(message.chat.id, f"{get_emj('process')} Finally, please send the payment confirmation screenshot or photo:", parse_mode="HTML")
        user_states[user_id] = "dep_waiting_photo"

# --- পেমেন্ট ফটো গ্রহণ হ্যান্ডলার ---
@bot.message_handler(content_types=['photo'], func=lambda message: user_states.get(message.from_user.id) == "dep_waiting_photo")
def handle_deposit_photo(message):
    user_id = message.from_user.id
    user_states[user_id] = None
    
    if user_id not in active_deposits:
        bot.send_message(message.chat.id, "Session expired.")
        return
        
    photo_id = message.photo[-1].file_id
    dep_data = active_deposits[user_id]
    
    method = dep_data["method"]
    amount = dep_data["amount"]
    sender_acc = dep_data["sender_acc"]
    txid = dep_data["txid"]
    
    markup = types.InlineKeyboardMarkup()
    app_btn = ibtn("Approve", callback_data=f"adm_dep_approve_{user_id}_{amount}", style="success", custom_emoji_id=get_emj_id("done"))
    rej_btn = ibtn("Reject", callback_data=f"adm_dep_reject_{user_id}", style="danger", custom_emoji_id=get_emj_id("wrong"))
    markup.add(app_btn, rej_btn)
    
    admin_text = (
        f"{get_emj('admin')} <b>New Deposit Request Received!</b>\n\n"
        f"User: {message.from_user.first_name} (ID: `{user_id}`)\n"
        f"{get_emj('wallet')} Method: {method}\n"
        f"{get_emj('money')} Amount: {amount} Tk\n"
        f"Sender Account: `{sender_acc}`\n"
        f"Transaction ID: `{txid}`"
    )
    
    bot.send_photo(SUPERADMIN_ID, photo_id, caption=admin_text, reply_markup=markup, parse_mode="HTML")
    bot.send_message(message.chat.id, f"{get_emj('process')} Your deposit details and screenshot have been successfully sent to admin. Please wait for verification.", parse_mode="HTML")
    active_deposits.pop(user_id, None)


# ==================================================
# --- DYNAMIC RENDERING HELPERS FOR ADMIN VIEWS ---
# ==================================================

# সিস্টেম কন্ট্রোল উইন্ডো রেন্ডারার (মেইনটেন্যান্স ফিক্স সহ - বাটন রিমেক)
def render_system_control_menu(chat_id, message_id):
    db = load_db()
    is_maint = db.get("maintenance", False)
    
    m_mode_label = f"{get_emj('done')} <b>ENABLED (ON)</b>" if is_maint else f"{get_emj('wrong')} <b>DISABLED (OFF)</b>"
    btn_maint_text = "🟢 Turn Maintenance OFF" if is_maint else "🔴 Turn Maintenance ON"
    
    text = (
        f"{get_emj('admin_panel')} <b>System Control Center</b>\n\n"
        f"• Maintenance Mode Status: {m_mode_label}\n\n"
        f"Perform instant platform tasks using buttons below:"
    )
    markup = InlineKeyboardMarkup(row_width=2)
    btn_maint = ibtn(btn_maint_text, callback_data="adm_sys_toggle_maint", style="primary", custom_emoji_id=get_emj_id("admin_panel"))
    btn_backup = ibtn("Backup Database", callback_data="adm_sys_backupdb", style="primary", custom_emoji_id=get_emj_id("extracting"))
    btn_clean = ibtn("Wipe Logs", callback_data="adm_sys_cleanlogs", style="primary", custom_emoji_id=get_emj_id("delete"))
    btn_kill = ibtn("Stop All Bots", callback_data="adm_sys_killall", style="danger", custom_emoji_id=get_emj_id("stop"))
    btn_back = ibtn("Back", callback_data="admin_menu_main", style="danger", custom_emoji_id=get_emj_id("wrong"))
    markup.add(btn_maint)
    markup.add(btn_backup, btn_clean)
    markup.add(btn_kill)
    markup.add(btn_back)
    try:
        bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode="HTML")
    except:
        pass

# প্যাকেজ কন্ট্রোল বোর্ড রেন্ডারার
def render_packages_menu(chat_id, message_id):
    db = load_db()
    plans = db.get("plans", {})
    text = f"{get_emj('products')} <b>Active Hosting Packages / Plans:</b>\n\n"
    if not plans:
        text += "No packages available. Use button below to add one!\n"
    else:
        for pid, pinfo in plans.items():
            text += f"• <b>ID:</b> <code>{pid}</code> | <b>{pinfo.get('name')}</b> | Cost: <code>{pinfo.get('cost')}</code> Tk | Validity: <code>{pinfo.get('days')}</code> Days\n"
    
    markup = InlineKeyboardMarkup(row_width=2)
    btn_add = ibtn("Add Package", callback_data="adm_pkg_add_prompt", style="success", custom_emoji_id=get_emj_id("add"))
    btn_edit = ibtn("Edit Package", callback_data="adm_pkg_edit_list", style="primary", custom_emoji_id=get_emj_id("admin_panel"))
    btn_del = ibtn("Delete Package", callback_data="adm_pkg_delete_list", style="danger", custom_emoji_id=get_emj_id("delete"))
    btn_back = ibtn("Back", callback_data="admin_menu_main", style="danger", custom_emoji_id=get_emj_id("wrong"))
    
    markup.add(btn_add)
    markup.add(btn_edit, btn_del)
    markup.add(btn_back)
    try:
        bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode="HTML")
    except:
        pass

# এডিট প্যাকেজ রেন্ডারার
def render_packages_edit_list(chat_id, message_id):
    db = load_db()
    plans = db.get("plans", {})
    if not plans:
        try: bot.edit_message_text("❌ No packages found to edit.", chat_id=chat_id, message_id=message_id)
        except: pass
        return
    text = "✏️ <b>Select Package to Edit:</b>"
    markup = InlineKeyboardMarkup(row_width=2)
    for pid, pinfo in plans.items():
        markup.add(ibtn(f"Edit {pinfo.get('name')}", callback_data=f"adm_pkg_edit_select_{pid}"))
    markup.add(ibtn("Back", callback_data="admin_menu_packages", style="danger", custom_emoji_id=get_emj_id("wrong")))
    try:
        bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode="HTML")
    except:
        pass

# ডিলিট প্যাকেজ রেন্ডারার
def render_packages_delete_list(chat_id, message_id):
    db = load_db()
    plans = db.get("plans", {})
    if not plans:
        try: bot.edit_message_text("❌ No packages found to delete.", chat_id=chat_id, message_id=message_id)
        except: pass
        return
    text = "🗑️ <b>Select Package to Delete:</b>"
    markup = InlineKeyboardMarkup(row_width=2)
    for pid, pinfo in plans.items():
        markup.add(ibtn(f"Delete {pinfo.get('name')}", callback_data=f"adm_pkg_delete_confirm_{pid}"))
    markup.add(ibtn("Back", callback_data="admin_menu_packages", style="danger", custom_emoji_id=get_emj_id("wrong")))
    try:
        bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode="HTML")
    except:
        pass

# মাল্টি-অ্যাডমিন সেটিংস উইন্ডো রেন্ডারার
def render_multiadmin_menu(chat_id, message_id):
    db = load_db()
    admins = db.setdefault("admins", [SUPERADMIN_ID])
    text = (
        f"👥 <b>Multi-Admin Settings Manager:</b>\n\n"
        f"Current Authorized Admin IDs:\n"
    )
    for adm in admins:
        marker = " [Superadmin]" if int(adm) == SUPERADMIN_ID else ""
        text += f"• <code>{adm}</code>{marker}\n"
    text += "\nOnly authorized admins can access the control panel."
    markup = InlineKeyboardMarkup(row_width=2)
    btn_add = ibtn("Add Admin ID", callback_data="adm_multi_add_prompt", style="success", custom_emoji_id=get_emj_id("add"))
    btn_remove = ibtn("Remove Admin ID", callback_data="adm_multi_remove_list", style="danger", custom_emoji_id=get_emj_id("delete"))
    btn_back = ibtn("Back", callback_data="admin_menu_main", style="danger", custom_emoji_id=get_emj_id("wrong"))
    markup.add(btn_add, btn_remove)
    markup.add(btn_back)
    try:
        bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode="HTML")
    except:
        pass

# প্রোমো কোড উইন্ডো রেন্ডারার (টাইম এবং লিমিট কনফিগারেশন সহ)
def render_promo_panel(chat_id, message_id):
    db = load_db()
    promos = db.get("promo_codes", {})
    text = f"{get_emj('gift')} <b>Promo Code Settings Manager:</b>\n\n"
    if not promos:
        text += "No active promo codes found.\n"
    else:
        for code, info in promos.items():
            exp = info.get("expiry") if info.get("expiry") else "Lifetime / No Expiry"
            text += f"• <b>{code}</b>: <code>{info.get('amount')} Tk</code> | Redeemed: <code>{len(info.get('used_by', []))}/{info.get('max_uses')}</code> | Expiry: <code>{exp}</code>\n"
    
    text += "\nGenerate or clear promo codes using the buttons below:"
    markup = InlineKeyboardMarkup(row_width=2)
    btn_create = ibtn("Create Custom Code", callback_data="adm_settings_create_promo")
    btn_rand = ibtn("Generate Random Code", callback_data="adm_settings_rand_promo")
    btn_clear = ibtn("Delete Promo Codes", callback_data="adm_settings_clear_promo")
    btn_back = ibtn("Back", callback_data="admin_menu_settings", style="danger", custom_emoji_id=get_emj_id("wrong"))
    markup.add(btn_create, btn_rand)
    markup.add(btn_clear)
    markup.add(btn_back)
    try:
        bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode="HTML")
    except:
        pass

# গ্লোবাল সেটিংস পেজ রেন্ডারার (রিমেক এবং বাগ ফিক্সড)
def render_global_settings_menu(chat_id, message_id):
    db = load_db()
    settings = db.setdefault("settings", {
        "default_slot_limit": 2,
        "trial_days": 1,
        "payment_bkash": "01706490391 (Personal Send Money)",
        "payment_rocket": "01706490391 (Personal Send Money)",
        "payment_nagad": "01706490391 (Personal Send Money)",
        "payment_binance": "Pay ID: 880516152"
    })
    
    text = (
        f"{get_emj('admin_panel')} <b>Global Platforms Control Settings</b>\n\n"
        f"<b>📱 Payment Numbers:</b>\n"
        f"• bKash: <code>{settings.get('payment_bkash', 'Not Set')}</code>\n"
        f"• Nagad: <code>{settings.get('payment_nagad', 'Not Set')}</code>\n"
        f"• Rocket: <code>{settings.get('payment_rocket', 'Not Set')}</code>\n"
        f"• Binance ID: <code>{settings.get('payment_binance', 'Not Set')}</code>\n\n"
        f"<b>⚙️ Server Defaults:</b>\n"
        f"• New User Slot Limit: <code>{settings.get('default_slot_limit', 2)} slots</code>\n"
        f"• New User Trial Period: <code>{settings.get('trial_days', 1)} Days</code>\n\n"
        f"Choose a setting below to adjust or update:"
    )
    
    markup = InlineKeyboardMarkup(row_width=2)
    b1 = ibtn("bKash Info", callback_data="adm_settings_payment_bkash", style="primary", custom_emoji_id=get_emj_id("bkash"))
    b2 = ibtn("Nagad Info", callback_data="adm_settings_payment_nagad", style="primary", custom_emoji_id=get_emj_id("nagad"))
    b3 = ibtn("Rocket Info", callback_data="adm_settings_payment_rocket", style="primary", custom_emoji_id=get_emj_id("rocket"))
    b4 = ibtn("Binance Info", callback_data="adm_settings_payment_binance", style="primary", custom_emoji_id=get_emj_id("binance"))
    b5 = ibtn("Slot Limit", callback_data="adm_settings_default_limit", style="primary", custom_emoji_id=get_emj_id("status_btn"))
    b6 = ibtn("Trial Days", callback_data="adm_settings_trial_days", style="primary", custom_emoji_id=get_emj_id("time"))
    btn_promo_mngr = ibtn("Promo Manager", callback_data="adm_settings_promo_panel", style="success", custom_emoji_id=get_emj_id("gift"))
    btn_back = ibtn("Back to Dashboard", callback_data="admin_menu_main", style="danger", custom_emoji_id=get_emj_id("wrong"))
    
    markup.add(b1, b2)
    markup.add(b3, b4)
    markup.add(b5, b6)
    markup.add(btn_promo_mngr)
    markup.add(btn_back)
    try:
        bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode="HTML")
    except:
        pass


# ==================================================
# --- NEW REDESIGNED INTERACTIVE ADMIN SYSTEM ---
# ==================================================

# প্রধান ইন্টারেক্টিভ অ্যাডমিন প্যানেল ভিউ
def show_admin_dashboard(chat_id, edit_message_id=None):
    db = load_db()
    
    active_count = 0
    for user_slots in running_bots.values():
        for process in user_slots.values():
            if process and process.poll() is None:
                active_count += 1
                
    total_users = len(db["users"])
    revenue = db.get("revenue", 0.0)
    m_mode = "ON" if db.get("maintenance", False) else "OFF"
    
    admin_text = (
        f"{get_emj('admin')} <b>Interactive Admin Control Panel</b>\n\n"
        f"{get_emj('stats')} <b>Quick Overview:</b>\n"
        f"• Active Running Bots: <code>{active_count}</code>\n"
        f"• Registered Users: <code>{total_users}</code>\n"
        f"• Total Revenue: <code>{revenue} Tk</code>\n"
        f"• Maintenance Mode: <code>{m_mode}</code>\n\n"
        f"Choose a category below to manage the hosting platform:"
    )
    
    markup = InlineKeyboardMarkup(row_width=2)
    btn_stats = ibtn("Stats & Dist", callback_data="admin_menu_stats", style="primary", custom_emoji_id=get_emj_id("status_btn"))
    btn_sys = ibtn("System Control", callback_data="admin_menu_sys", style="primary", custom_emoji_id=get_emj_id("admin_panel"))
    btn_users = ibtn("User Manager", callback_data="admin_menu_users", style="primary", custom_emoji_id=get_emj_id("support"))
    btn_bc = ibtn("Broadcaster", callback_data="admin_menu_bc", style="primary", custom_emoji_id=get_emj_id("broadcast"))
    
    btn_pkg = ibtn("Package Manager", callback_data="admin_menu_packages", style="success", custom_emoji_id=get_emj_id("products"))
    btn_settings = ibtn("Global Settings", callback_data="admin_menu_settings", style="primary", custom_emoji_id=get_emj_id("admin_panel"))
    
    # NEW MULTI-ADMIN BUTTON
    btn_multi = ibtn("Admin Manager", callback_data="admin_menu_multiadmin", style="primary", custom_emoji_id=get_emj_id("user"))
    
    btn_logs = ibtn("Audit Logs", callback_data="admin_menu_tx", style="primary", custom_emoji_id=get_emj_id("file"))
    btn_health = ibtn("Auto Restarter", callback_data="admin_menu_health", style="primary", custom_emoji_id=get_emj_id("process"))
    btn_close = ibtn("Close Panel", callback_data="admin_menu_close", style="danger", custom_emoji_id=get_emj_id("wrong"))
    
    markup.add(btn_stats, btn_sys)
    markup.add(btn_users, btn_bc)
    markup.add(btn_pkg, btn_settings)
    markup.add(btn_multi, btn_logs)
    markup.add(btn_health, btn_close)
    
    if edit_message_id:
        try:
            bot.edit_message_text(admin_text, chat_id=chat_id, message_id=edit_message_id, reply_markup=markup, parse_mode="HTML")
        except:
            bot.send_message(chat_id, admin_text, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(chat_id, admin_text, reply_markup=markup, parse_mode="HTML")

# ইউজার ম্যানেজমেন্ট সাব-প্রোফাইল কার্ড
def manage_user_profile(chat_id, target_id, edit_message_id=None):
    db = load_db()
    target_str = str(target_id)
    if target_str not in db["users"]:
        bot.send_message(chat_id, "❌ User not found in database.")
        return
        
    user = db["users"][target_str]
    is_banned = target_str in db.get("banned_users", [])
    
    text = (
        f"👤 <b>Dynamic User Profile Manager</b>\n\n"
        f"• <b>User ID:</b> <code>{target_id}</code>\n"
        f"• <b>Username:</b> @{user.get('username', 'N/A')}\n"
        f"• {get_emj('money')} <b>Balance:</b> <code>{user.get('balance', 0.0)}</code> Tk\n"
        f"• {get_emj('products')} <b>Current Plan:</b> <code>{user.get('plan', 'NONE')}</code>\n"
        f"• {get_emj('time')} <b>Expiry Date:</b> <code>{user.get('plan_expiry') if user.get('plan_expiry') else 'N/A'}</code>\n"
        f"• Slot Limit: <code>{user.get('slot_limit', 2)}</code> slots\n"
        f"• Banned Status: <code>{'Yes' if is_banned else 'No'}</code>"
    )
    
    markup = InlineKeyboardMarkup(row_width=2)
    btn_add_money = ibtn("Add Balance", callback_data=f"adm_usr_addmoney_{target_id}", style="primary", custom_emoji_id=get_emj_id("add"))
    btn_ded_money = ibtn("Deduct Balance", callback_data=f"adm_usr_dedmoney_{target_id}", style="primary", custom_emoji_id=get_emj_id("money"))
    btn_add_plan = ibtn("Grant Plan", callback_data=f"adm_usr_addplan_{target_id}", style="primary", custom_emoji_id=get_emj_id("products"))
    btn_rem_plan = ibtn("Cancel Plan", callback_data=f"adm_usr_remplan_{target_id}", style="danger", custom_emoji_id=get_emj_id("delete"))
    btn_ban = ibtn("Unban" if is_banned else "Ban Account", callback_data=f"adm_usr_ban_{target_id}", style="danger", custom_emoji_id=get_emj_id("warning"))
    btn_limit = ibtn("Change Limit", callback_data=f"adm_usr_limit_{target_id}", style="primary", custom_emoji_id=get_emj_id("time"))
    
    # Browse project files & Send custom text direct alert
    btn_files = ibtn("Browse Files", callback_data=f"adm_usr_files_{target_id}", style="success", custom_emoji_id=get_emj_id("file"))
    btn_msg = ibtn("Send Alert", callback_data=f"adm_usr_msg_{target_id}", style="primary", custom_emoji_id=get_emj_id("broadcast"))
    
    btn_back = ibtn("Back to User Menu", callback_data="admin_menu_users", style="danger", custom_emoji_id=get_emj_id("wrong"))
    
    markup.add(btn_add_money, btn_ded_money)
    markup.add(btn_add_plan, btn_rem_plan)
    markup.add(btn_ban, btn_limit)
    markup.add(btn_files, btn_msg)
    markup.add(btn_back)
    
    if edit_message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=edit_message_id, reply_markup=markup, parse_mode="HTML")
        except:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")

# --- অ্যাডমিন স্ল্যাশ কমান্ড টু ভিউ কোড ফাইলস ---
@bot.message_handler(commands=['viewfile'])
def handle_view_file_cmd(message):
    if not is_admin(message.from_user.id): return
    try:
        parts = message.text.split(maxsplit=3)
        if len(parts) < 4:
            bot.send_message(message.chat.id, "❌ Usage: `/viewfile <USER_ID> <SLOT> <RELATIVE_FILE_PATH>`", parse_mode="Markdown")
            return
            
        target_id = parts[1]
        slot = parts[2]
        filepath = parts[3]
        
        full_path = os.path.abspath(os.path.join(f"hosted_bots/{target_id}/{slot}", filepath))
        base_dir = os.path.abspath(f"hosted_bots/{target_id}/{slot}")
        
        if not full_path.startswith(base_dir):
            bot.send_message(message.chat.id, "❌ Directory traversal blocked!")
            return
            
        if not os.path.exists(full_path):
            bot.send_message(message.chat.id, "❌ File not found.")
            return
            
        if os.path.getsize(full_path) > 1024 * 50: # max 50KB for text preview
            with open(full_path, 'rb') as f:
                bot.send_document(message.chat.id, f, caption=f"📄 {filepath}")
        else:
            with open(full_path, 'r', errors='ignore') as f:
                content = f.read()
            if not content.strip():
                content = "File is empty."
            bot.send_message(message.chat.id, f"📄 <b>File:</b> <code>{filepath}</code>\n\n```python\n{content}\n```", parse_mode="HTML")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

# --- অ্যাডমিন ইনপুট স্টেটস হ্যান্ডলার (টেক্সট ইনপুটের জন্য - মাল্টি-অ্যাডমিন ফিক্সড) ---
@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and user_states.get(message.from_user.id) is not None)
def handle_admin_text_inputs(message):
    user_id = message.from_user.id
    state = user_states[user_id]
    db = load_db()
    user_states[user_id] = None  # স্টেট ক্লিয়ার করা (মাল্টি-অ্যাডমিন ফিক্সড)
    
    if state == "adm_wait_user_id":
        target_id = message.text.strip()
        if target_id in db["users"]:
            manage_user_profile(message.chat.id, target_id)
        else:
            bot.send_message(message.chat.id, "❌ User ID not found in database. Please try again.")
            
    elif state.startswith("adm_state_addmoney_"):
        target_id = state.replace("adm_state_addmoney_", "")
        try:
            amount = float(message.text)
            target_user = get_user(target_id, db)
            target_user["balance"] += amount
            db.setdefault("tx_logs", []).append({
                "user_id": str(target_id),
                "type": "BALANCE_ADD",
                "amount": amount,
                "detail": "Admin direct add",
                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            save_db(db)
            bot.send_message(message.chat.id, f"Successfully added <code>{amount}</code> Tk to User ID <code>{target_id}</code>.", parse_mode="HTML")
            try:
                bot.send_message(target_id, f"{get_emj('money')} Admin has added <b>{amount}</b> Tk directly to your wallet!", parse_mode="HTML")
            except: pass
            manage_user_profile(message.chat.id, target_id)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid value. Please send a valid number.")
            
    elif state.startswith("adm_state_dedmoney_"):
        target_id = state.replace("adm_state_dedmoney_", "")
        try:
            amount = float(message.text)
            target_user = get_user(target_id, db)
            target_user["balance"] = max(0.0, target_user["balance"] - amount)
            db.setdefault("tx_logs", []).append({
                "user_id": str(target_id),
                "type": "BALANCE_DEDUCT",
                "amount": amount,
                "detail": "Admin direct deduct",
                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            save_db(db)
            bot.send_message(message.chat.id, f"Successfully deducted <code>{amount}</code> Tk from User ID <code>{target_id}</code>.", parse_mode="HTML")
            try:
                bot.send_message(target_id, f"{get_emj('warning')} Admin has deducted <b>{amount}</b> Tk from your wallet.", parse_mode="HTML")
            except: pass
            manage_user_profile(message.chat.id, target_id)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid value. Please send a valid number.")
            
    elif state.startswith("adm_state_addplan_"):
        target_id = state.replace("adm_state_addplan_", "")
        try:
            days = int(message.text)
            target_user = get_user(target_id, db)
            expiry_date = datetime.datetime.now() + datetime.timedelta(days=days)
            expiry_str = expiry_date.strftime("%Y-%m-%d %H:%M:%S")
            target_user["plan"] = f"Admin Plan ({days} Days)"
            target_user["plan_expiry"] = expiry_str
            save_db(db)
            bot.send_message(message.chat.id, f"Successfully granted <code>{days}</code>-day plan to User ID <code>{target_id}</code>.", parse_mode="HTML")
            try:
                bot.send_message(target_id, f"Admin has granted you an active plan for <b>{days} days</b>! Expiry: {expiry_str}", parse_mode="HTML")
            except: pass
            manage_user_profile(message.chat.id, target_id)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid days format. Please send an integer.")
            
    elif state.startswith("adm_state_setlimit_"):
        target_id = state.replace("adm_state_setlimit_", "")
        try:
            limit = int(message.text)
            target_user = get_user(target_id, db)
            target_user["slot_limit"] = limit
            save_db(db)
            bot.send_message(message.chat.id, f"Successfully set slot limit to <code>{limit}</code> slots for User ID <code>{target_id}</code>.", parse_mode="HTML")
            try:
                bot.send_message(target_id, f"Your hosting slot limit has been updated to <b>{limit}</b> slots!", parse_mode="HTML")
            except: pass
            manage_user_profile(message.chat.id, target_id)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid limit. Please send an integer.")
            
    elif state == "adm_wait_bc_msg":
        msg_text = message.text.strip()
        if not msg_text:
            bot.send_message(message.chat.id, "❌ Cannot send empty broadcast.")
            return
            
        total_users = len(db["users"])
        success_count = 0
        bot.send_message(message.chat.id, f"Sending broadcast message to {total_users} users...")
        for uid in db["users"].keys():
            try:
                bot.send_message(uid, f"{get_emj('broadcast')} <b>Platform Notice:</b>\n\n{msg_text}", parse_mode="HTML")
                success_count += 1
            except:
                continue
        bot.send_message(message.chat.id, f"Broadcast completed successfully for {success_count}/{total_users} users.")

    elif state.startswith("adm_usr_sendalert_"):
        target_id = state.replace("adm_usr_sendalert_", "")
        alert_msg = message.text.strip()
        try:
            bot.send_message(target_id, f"{get_emj('broadcast')} <b>Personal Direct Alert from Admin:</b>\n\n{alert_msg}", parse_mode="HTML")
            bot.send_message(message.chat.id, f"Alert sent successfully to User ID <code>{target_id}</code>.", parse_mode="HTML")
            manage_user_profile(message.chat.id, target_id)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Failed to send alert: {str(e)}")

    elif state.startswith("adm_set_payment_"):
        pay_type = state.replace("adm_set_payment_", "")
        val = message.text.strip()
        settings = db.setdefault("settings", {})
        
        if pay_type == "bkash": settings["payment_bkash"] = val
        elif pay_type == "nagad": settings["payment_nagad"] = val
        elif pay_type == "rocket": settings["payment_rocket"] = val
        elif pay_type == "binance": settings["payment_binance"] = val
        
        save_db(db)
        bot.send_message(message.chat.id, f"System payment detail for {pay_type.upper()} updated successfully!")
        show_admin_dashboard(message.chat.id)

    # TEXT INGESTIONS FOR PACKAGE MANAGER CREATING FLOW
    elif state == "adm_wait_pkg_add_id":
        pkg_id = message.text.strip().lower()
        if pkg_id in db.get("plans", {}):
            bot.send_message(message.chat.id, "❌ This Package ID already exists! Please enter a unique ID:")
            user_states[user_id] = "adm_wait_pkg_add_id"
            return
        user_states[user_id] = f"adm_wait_pkg_add_name_{pkg_id}"
        bot.send_message(message.chat.id, f"Send Plan Name for Package ID <code>{pkg_id}</code> (e.g., Premium VPS):", parse_mode="HTML")
        
    elif state.startswith("adm_wait_pkg_add_name_"):
        pkg_id = state.replace("adm_wait_pkg_add_name_", "")
        pkg_name = message.text.strip()
        user_states[user_id] = f"adm_wait_pkg_add_cost_{pkg_id}_{pkg_name}"
        bot.send_message(message.chat.id, f"Send cost in Tk for plan <b>{pkg_name}</b> (Numbers only, e.g. 199):", parse_mode="HTML")
        
    elif state.startswith("adm_wait_pkg_add_cost_"):
        parts = state.replace("adm_wait_pkg_add_cost_", "").split("_", 1)
        pkg_id = parts[0]
        pkg_name = parts[1]
        try:
            cost = float(message.text.strip())
            user_states[user_id] = f"adm_wait_pkg_add_days_{pkg_id}_{pkg_name}_{cost}"
            bot.send_message(message.chat.id, f"Send validity in days for plan <b>{pkg_name}</b> (Cost: {cost} Tk):", parse_mode="HTML")
        except ValueError:
            user_states[user_id] = state
            bot.send_message(message.chat.id, "❌ Please enter a valid number for cost:")
            
    elif state.startswith("adm_wait_pkg_add_days_"):
        parts = state.replace("adm_wait_pkg_add_days_", "").split("_", 2)
        pkg_id = parts[0]
        pkg_name = parts[1]
        cost = float(parts[2])
        try:
            days = int(message.text.strip())
            plans = db.setdefault("plans", {})
            plans[pkg_id] = {
                "name": pkg_name,
                "cost": cost,
                "days": days
            }
            save_db(db)
            bot.send_message(message.chat.id, f"✅ Package <b>{pkg_name}</b> (ID: {pkg_id}) successfully created!", parse_mode="HTML")
            show_admin_dashboard(message.chat.id)
        except ValueError:
            user_states[user_id] = state
            bot.send_message(message.chat.id, "❌ Please enter a valid integer for validity days:")

    # TEXT INGESTIONS FOR PACKAGE MANAGER EDITING FLOW
    elif state.startswith("adm_wait_pkg_edit_"):
        parts = state.replace("adm_wait_pkg_edit_", "").split("_", 1)
        pid = parts[0]
        field = parts[1]
        val = message.text.strip()
        
        plans = db.get("plans", {})
        if pid in plans:
            if field == "name":
                plans[pid]["name"] = val
            elif field == "cost":
                try:
                    plans[pid]["cost"] = float(val)
                except ValueError:
                    bot.send_message(message.chat.id, "❌ Invalid cost. Please enter a valid number.")
                    return
            elif field == "days":
                try:
                    plans[pid]["days"] = int(val)
                except ValueError:
                    bot.send_message(message.chat.id, "❌ Invalid validity days. Please enter an integer.")
                    return
                    
            save_db(db)
            bot.send_message(message.chat.id, f"Package {field.upper()} updated successfully!")
            show_admin_dashboard(message.chat.id)

    # SETTING DYNAMIC ADJUSTERS
    elif state == "adm_set_default_limit":
        try:
            limit = int(message.text.strip())
            settings = db.setdefault("settings", {})
            settings["default_slot_limit"] = limit
            save_db(db)
            bot.send_message(message.chat.id, f"Default slot limit set to {limit} successfully!")
            show_admin_dashboard(message.chat.id)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Please enter a valid integer.")
            
    elif state == "adm_set_trial_days":
        try:
            days = int(message.text.strip())
            settings = db.setdefault("settings", {})
            settings["trial_days"] = days
            save_db(db)
            bot.send_message(message.chat.id, f"Default trial validity days set to {days} successfully!")
            show_admin_dashboard(message.chat.id)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Please enter a valid integer.")

    # MULTI-ADMIN ID ADDITION STATE
    elif state == "adm_wait_multi_add_id":
        try:
            new_adm = int(message.text.strip())
            admins = db.setdefault("admins", [SUPERADMIN_ID])
            if new_adm not in admins:
                admins.append(new_adm)
                save_db(db)
                bot.send_message(message.chat.id, f"✅ User ID <code>{new_adm}</code> authorized as Admin successfully!", parse_mode="HTML")
            else:
                bot.send_message(message.chat.id, "❌ This User ID is already an Admin.")
            show_admin_dashboard(message.chat.id)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Please enter a valid numerical User ID.")

    # NEW: REDEEM CODE MULTI-STEP GENERATION COMPONENTS (PROMO SYSTEM FULLY RE-BUILT)
    elif state == "adm_wait_promo_name":
        code_name = message.text.strip().upper()
        # স্পেস বা ইমোজি হ্যান্ডলিং ও সিকিউরিটি চেক
        if " " in code_name or len(code_name) < 3:
            bot.send_message(message.chat.id, "❌ Invalid Promo Code. Use continuous characters (e.g. GET50) with no spaces.")
            user_states[user_id] = "adm_wait_promo_name"
            return
        if code_name in db.get("promo_codes", {}):
            bot.send_message(message.chat.id, "❌ This Promo Code already exists! Enter a unique name:")
            user_states[user_id] = "adm_wait_promo_name"
            return
        user_states[user_id] = f"adm_wait_promo_amount_{code_name}"
        bot.send_message(message.chat.id, f"Please send Reward balance in Tk for Promo Code <b>{code_name}</b> (e.g. 100):", parse_mode="HTML")

    elif state.startswith("adm_wait_promo_amount_"):
        code_name = state.replace("adm_wait_promo_amount_", "")
        try:
            amount = float(message.text.strip())
            if amount <= 0:
                bot.send_message(message.chat.id, "❌ Please send a positive numerical amount:")
                user_states[user_id] = state
                return
            user_states[user_id] = f"adm_wait_promo_limit_{code_name}_{amount}"
            bot.send_message(message.chat.id, f"Please send redemption limit (Maximum user claims, e.g. 50):", parse_mode="HTML")
        except ValueError:
            user_states[user_id] = state
            bot.send_message(message.chat.id, "❌ Invalid format. Please enter a valid number for reward amount:")

    elif state.startswith("adm_wait_promo_limit_"):
        parts = state.replace("adm_wait_promo_limit_", "").split("_")
        code_name = parts[0]
        amount = float(parts[1])
        try:
            limit = int(message.text.strip())
            if limit <= 0:
                bot.send_message(message.chat.id, "❌ Limit must be a positive integer:")
                user_states[user_id] = state
                return
            user_states[user_id] = f"adm_wait_promo_expiry_{code_name}_{amount}_{limit}"
            bot.send_message(message.chat.id, f"Please enter Promo Code validity duration in **HOURS** (e.g. 24 for 1 day, or enter 0 for lifetime / no expiry limit):", parse_mode="HTML")
        except ValueError:
            user_states[user_id] = state
            bot.send_message(message.chat.id, "❌ Invalid format. Please enter an integer limit:")

    elif state.startswith("adm_wait_promo_expiry_"):
        parts = state.replace("adm_wait_promo_expiry_", "").split("_")
        code_name = parts[0]
        amount = float(parts[1])
        limit = int(parts[2])
        try:
            hours = int(message.text.strip())
            if hours < 0:
                bot.send_message(message.chat.id, "❌ Validity hours cannot be negative:")
                user_states[user_id] = state
                return
                
            expiry_str = None
            if hours > 0:
                expiry_dt = datetime.datetime.now() + datetime.timedelta(hours=hours)
                expiry_str = expiry_dt.strftime("%Y-%m-%d %H:%M:%S")
                
            promos = db.setdefault("promo_codes", {})
            promos[code_name] = {
                "amount": amount,
                "max_uses": limit,
                "used_by": [],
                "expiry": expiry_str
            }
            save_db(db)
            
            exp_label = f"{hours} Hours (Expires: {expiry_str})" if expiry_str else "Lifetime / No Expiry"
            bot.send_message(message.chat.id, f"✅ Promo Code <b>{code_name}</b> successfully generated!\n\nReward: {amount} Tk\nLimit: {limit} users\nValidity: {exp_label}", parse_mode="HTML")
            show_admin_dashboard(message.chat.id)
        except ValueError:
            user_states[user_id] = state
            bot.send_message(message.chat.id, "❌ Invalid format. Please enter an integer value for validity hours:")


# --- ইন্টারেক্টিভ অ্যাডমিন কলব্যাক রিসিভার ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_menu_") or call.data.startswith("adm_sys_") or call.data.startswith("adm_usr_") or call.data.startswith("adm_settings_") or call.data.startswith("adm_pkg_") or call.data.startswith("adm_multi_"))
def handle_admin_panel_clicks(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        bot.answer_callback_query(call.id, "Access Denied.")
        return
        
    db = load_db()
    data = call.data
    bot.answer_callback_query(call.id)
    
    if data == "admin_menu_main":
        show_admin_dashboard(call.message.chat.id, edit_message_id=call.message.message_id)
        
    elif data == "admin_menu_stats":
        active_count = 0
        for user_slots in running_bots.values():
            for process in user_slots.values():
                if process and process.poll() is None:
                    active_count += 1
        total_users = len(db["users"])
        revenue = db.get("revenue", 0.0)
        
        if HAS_PSUTIL:
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent
            sys_info_str = f"CPU Usage: {cpu}% | RAM: {ram}% | Disk: {disk}%"
        else:
            sys_info_str = "psutil library not available on system"
            
        distribution = {}
        for uid, udata in db["users"].items():
            p = udata.get("plan", "NONE")
            distribution[p] = distribution.get(p, 0) + 1
            
        dist_str = ""
        for plan, count in distribution.items():
            dist_str += f"  • {plan}: <code>{count}</code> users\n"
            
        stats_text = (
            f"<b>Detailed Platform Stats</b>\n\n"
            f"• <b>Total Registered Users:</b> <code>{total_users}</code>\n"
            f"• <b>Active Running Bots:</b> <code>{active_count}</code>\n"
            f"• <b>Total Plan Revenue:</b> <code>{revenue} Tk</code>\n\n"
            f"🖥️ <b>Server Resources:</b>\n"
            f"  {sys_info_str}\n\n"
            f"📋 <b>Active Plans Distribution:</b>\n"
            f"{dist_str if dist_str else '  No plans active yet.'}"
        )
        markup = InlineKeyboardMarkup()
        markup.add(ibtn("Back", callback_data="admin_menu_main", style="danger", custom_emoji_id=get_emj_id("wrong")))
        bot.edit_message_text(stats_text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="HTML")
        
    elif data == "admin_menu_sys":
        render_system_control_menu(call.message.chat.id, call.message.message_id)
        
    # মেইনটেন্যান্স অন/অফ লাইভ ফিক্সড ফ্লো
    elif data == "adm_sys_toggle_maint":
        current = db.get("maintenance", False)
        db["maintenance"] = not current
        save_db(db)
        bot.answer_callback_query(call.id, f"Maintenance is now {'ON' if db['maintenance'] else 'OFF'}")
        render_system_control_menu(call.message.chat.id, call.message.message_id)
        
    elif data == "adm_sys_backupdb":
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'rb') as f:
                bot.send_document(call.message.chat.id, f, caption="Database Backup Archive")
        else:
            bot.answer_callback_query(call.id, "DB File not found.")
            
    elif data == "adm_sys_cleanlogs":
        count = 0
        for root, dirs, files in os.walk("hosted_bots"):
            for file in files:
                if file.endswith(".log"):
                    try:
                        os.remove(os.path.join(root, file))
                        count += 1
                    except:
                        pass
        bot.answer_callback_query(call.id, f"Wiped {count} log files!")
        
    elif data == "adm_sys_killall":
        count = 0
        for user_id, slots in list(running_bots.items()):
            for slot in list(slots.keys()):
                if stop_bot_process(user_id, slot):
                    count += 1
        bot.answer_callback_query(call.id, f"Terminated {count} bots.")
        
    elif data == "admin_menu_users":
        text = (
            f"<b>User Management Console</b>\n\n"
            f"Manage platform subscribers and credits efficiently:"
        )
        markup = InlineKeyboardMarkup(row_width=1)
        btn_search = ibtn("Search / Edit User Profile", callback_data="adm_sys_usr_search", style="primary", custom_emoji_id=get_emj_id("support"))
        btn_list = ibtn("View Registered Users List (Inline)", callback_data="adm_sys_usr_list", style="primary", custom_emoji_id=get_emj_id("broadcast"))
        btn_list_txt = ibtn("Download User List (TXT)", callback_data="adm_sys_usr_list_txt", style="success", custom_emoji_id=get_emj_id("file"))
        btn_back = ibtn("Back", callback_data="admin_menu_main", style="danger", custom_emoji_id=get_emj_id("wrong"))
        markup.add(btn_search, btn_list, btn_list_txt, btn_back)
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="HTML")
        
    elif data == "adm_sys_usr_search":
        user_states[user_id] = "adm_wait_user_id"
        bot.send_message(call.message.chat.id, "Please enter or send the <b>User ID</b> you wish to search:")
        
    elif data == "adm_sys_usr_list":
        users_list = f"{get_emj('admin')} <b>Registered Users Database:</b>\n\n"
        for uid, udata in db["users"].items():
            users_list += (
                f"👤 <b>ID:</b> <code>{uid}</code>\n"
                f"👤 <b>Username:</b> @{udata.get('username', 'N/A')}\n"
                f"💵 <b>Balance:</b> {udata.get('balance', 0.0)} Tk\n"
                f"📦 <b>Plan:</b> {udata.get('plan', 'NONE')}\n"
                f"⚡ <b>Slots Limit:</b> {udata.get('slot_limit', 2)} bots\n"
                f"--------------------\n"
            )
            if len(users_list) > 3000:
                bot.send_message(call.message.chat.id, users_list, parse_mode="HTML")
                users_list = ""
        if users_list:
            bot.send_message(call.message.chat.id, users_list, parse_mode="HTML")

    elif data == "adm_sys_usr_list_txt":
        file_path = "user_database_report.txt"
        
        report = (
            "============================================================\n"
            "                 REGISTERED USERS DATABASE REPORT           \n"
            f"                 Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            "============================================================\n\n"
        )
        
        report += f"{'USER ID':<15} | {'USERNAME':<18} | {'BALANCE':<10} | {'PLAN':<18} | {'VAL_DAYS':<15}\n"
        report += "-" * 85 + "\n"
        
        for uid, udata in db.get("users", {}).items():
            username = udata.get("username", "N/A")
            if username != "N/A":
                username = f"@{username}"
            balance = f"{udata.get('balance', 0.0)} Tk"
            plan = udata.get("plan", "NONE")
            
            expiry_str = udata.get("plan_expiry")
            days_left = "N/A"
            if expiry_str:
                try:
                    expiry = datetime.datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
                    delta = expiry - datetime.datetime.now()
                    if delta.days >= 0:
                        days_left = f"{delta.days + 1} Days"
                    else:
                        days_left = "Expired"
                except:
                    days_left = "Error"
                    
            report += f"{uid:<15} | {username:<18} | {balance:<10} | {plan:<18} | {days_left:<15}\n"
            
        report += "\n============================================================\n"
        report += f"Total registered users found: {len(db.get('users', {}))}\n"
        report += "============================================================\n"
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report)
            
        with open(file_path, "rb") as f:
            bot.send_document(call.message.chat.id, f, caption="Registered Users Database TXT Report")
            
        try: os.remove(file_path)
        except: pass
            
    elif data == "admin_menu_bc":
        text = (
            f"📢 <b>Global Broadcast Portal</b>\n\n"
            f"Push announcements to all registered user inbox instantly."
        )
        markup = InlineKeyboardMarkup()
        btn_start_bc = ibtn("Push Broadcast Message", callback_data="adm_sys_bc_start", style="success", custom_emoji_id=get_emj_id("broadcast"))
        btn_back = ibtn("Back", callback_data="admin_menu_main", style="danger", custom_emoji_id=get_emj_id("wrong"))
        markup.add(btn_start_bc, btn_back)
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="HTML")
        
    elif data == "adm_sys_bc_start":
        user_states[user_id] = "adm_wait_bc_msg"
        bot.send_message(call.message.chat.id, "Please send the text message you wish to broadcast:")
        
    elif data == "admin_menu_close":
        bot.delete_message(call.message.chat.id, call.message.message_id)

    # DYNAMIC PACKAGE MANAGER COMPONENT VIEWS (ADD, EDIT, DELETE - ALL RECURSION REMOVED)
    elif data == "admin_menu_packages":
        render_packages_menu(call.message.chat.id, call.message.message_id)

    elif data == "adm_pkg_add_prompt":
        user_states[user_id] = "adm_wait_pkg_add_id"
        bot.send_message(call.message.chat.id, "Send unique ID for new plan (e.g., <code>5</code> or <code>vip</code>):", parse_mode="HTML")

    elif data == "adm_pkg_edit_list":
        render_packages_edit_list(call.message.chat.id, call.message.message_id)
        
    elif data.startswith("adm_pkg_edit_select_"):
        pid = data.replace("adm_pkg_edit_select_", "")
        pinfo = db.get("plans", {}).get(pid, {})
        text = (
            f"✏️ <b>Edit Package ID:</b> <code>{pid}</code>\n\n"
            f"• <b>Name:</b> {pinfo.get('name')}\n"
            f"• <b>Cost:</b> {pinfo.get('cost')} Tk\n"
            f"• <b>Validity:</b> {pinfo.get('days')} Days\n\n"
            f"Select what to edit:"
        )
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(ibtn("Edit Name", callback_data=f"adm_pkg_edit_field_{pid}_name"))
        markup.add(ibtn("Edit Cost", callback_data=f"adm_pkg_edit_field_{pid}_cost"))
        markup.add(ibtn("Edit Days", callback_data=f"adm_pkg_edit_field_{pid}_days"))
        markup.add(ibtn("Back", callback_data="adm_pkg_edit_list", style="danger", custom_emoji_id=get_emj_id("wrong")))
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="HTML")
        
    elif data.startswith("adm_pkg_edit_field_"):
        parts = data.replace("adm_pkg_edit_field_", "").split("_", 1)
        pid = parts[0]
        field = parts[1]
        user_states[user_id] = f"adm_wait_pkg_edit_{pid}_{field}"
        bot.send_message(call.message.chat.id, f"Send new value for package {field.upper()}:")

    elif data == "adm_pkg_delete_list":
        render_packages_delete_list(call.message.chat.id, call.message.message_id)
        
    elif data.startswith("adm_pkg_delete_confirm_"):
        pid = data.replace("adm_pkg_delete_confirm_", "")
        plans = db.get("plans", {})
        if pid in plans:
            del_name = plans[pid].get("name", "Plan")
            del plans[pid]
            save_db(db)
            bot.answer_callback_query(call.id, f"Package {del_name} deleted!")
        render_packages_delete_list(call.message.chat.id, call.message.message_id)

    # GLOBAL SETTINGS ADJUSTERS (REMAKE AND BUG FIXED)
    elif data == "admin_menu_settings":
        render_global_settings_menu(call.message.chat.id, call.message.message_id)

    elif data.startswith("adm_settings_payment_"):
        pay_type = data.replace("adm_settings_payment_", "")
        user_states[user_id] = f"adm_set_payment_{pay_type}"
        bot.send_message(call.message.chat.id, f"Please send the new text value for {pay_type.upper()}:")

    elif data == "adm_settings_default_limit":
        user_states[user_id] = "adm_set_default_limit"
        bot.send_message(call.message.chat.id, "Please enter the default slot limit (integer):")
        
    elif data == "adm_settings_trial_days":
        user_states[user_id] = "adm_set_trial_days"
        bot.send_message(call.message.chat.id, "Please enter the default trial duration in days (integer):")

    # NEW: PROMO CODES / REDEEM CODES MANAGER (LATEST UPGRADE)
    elif data == "adm_settings_promo_panel":
        render_promo_panel(call.message.chat.id, call.message.message_id)

    elif data == "adm_settings_create_promo":
        user_states[user_id] = "adm_wait_promo_name"
        bot.send_message(call.message.chat.id, f"{get_emj('gift')} Please enter unique <b>Promo Code name</b> with no spaces (e.g. <code>GET50</code>):", parse_mode="HTML")

    elif data == "adm_settings_rand_promo":
        # AUTO-GENERATION ALGORITHM ( limit and time config follows next)
        rand_code = "GIFT-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        user_states[user_id] = f"adm_wait_promo_amount_{rand_code}"
        bot.send_message(call.message.chat.id, f"🎲 Auto-Generated Code: <b>{rand_code}</b>\n\nPlease enter the reward balance **Amount** (Tk) for this code:", parse_mode="HTML")

    elif data == "adm_settings_clear_promo":
        db["promo_codes"] = {}
        save_db(db)
        bot.answer_callback_query(call.id, "Promo codes cleared successfully!")
        render_promo_panel(call.message.chat.id, call.message.message_id)

    # AUDIT LOGS / TX HISTORY
    elif data == "admin_menu_tx":
        txs = db.get("tx_logs", [])
        text = f"<b>Recent Audit & Tx Logs:</b>\n\n"
        if not txs:
            text += "No transactions recorded yet."
        else:
            for item in txs[-15:]:
                text += f"• <code>{item.get('date')}</code>: User <code>{item.get('user_id')}</code> - {item.get('type')} ({item.get('amount')} Tk) [{item.get('detail', '')}]\n"
        
        markup = InlineKeyboardMarkup()
        btn_back = ibtn("Back", callback_data="admin_menu_main", style="danger", custom_emoji_id=get_emj_id("wrong"))
        markup.add(btn_back)
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # HEALTH MONITOR / ALIVE RESTARTER
    elif data == "admin_menu_health":
        active_recovered = 0
        active_users = []
        for uid, udata in db.get("users", {}).items():
            if is_plan_active(uid, db):
                active_users.append(uid)
                limit = udata.get("slot_limit", 2)
                for i in range(1, limit + 1):
                    slot_name = f"slot{i}"
                    status = get_bot_status(uid, slot_name)
                    slot_dir = f"hosted_bots/{uid}/{slot_name}"
                    if status == "STOPPED" and os.path.exists(slot_dir) and find_entrypoint(slot_dir):
                        success, res = start_bot_process(uid, slot_name)
                        if success: active_recovered += 1
                            
        text = (
            f"<b>Health Status Monitor & Auto-Recovery</b>\n\n"
            f"• Scanned {len(active_users)} Active Users Hosting slots.\n"
            f"• Recovered & Auto-Restarted: <b>{active_recovered}</b> crashed bots!\n\n"
            f"All active user bots are now running healthy on the host server!"
        )
        markup = InlineKeyboardMarkup()
        btn_back = ibtn("Back", callback_data="admin_menu_main", style="danger", custom_emoji_id=get_emj_id("wrong"))
        markup.add(btn_back)
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # MULTI-ADMIN COMPONENT INTERFACES
    elif data == "admin_menu_multiadmin":
        render_multiadmin_menu(call.message.chat.id, call.message.message_id)

    elif data == "adm_multi_add_prompt":
        user_states[user_id] = "adm_wait_multi_add_id"
        bot.send_message(call.message.chat.id, "Please enter the Telegram **User ID** to grant Admin permissions:")

    elif data == "adm_multi_remove_list":
        db_admins = db.setdefault("admins", [SUPERADMIN_ID])
        text = "🗑️ <b>Select Admin ID to Remove:</b>"
        markup = InlineKeyboardMarkup(row_width=2)
        for adm in db_admins:
            if int(adm) != SUPERADMIN_ID:
                markup.add(ibtn(f"Remove {adm}", callback_data=f"adm_multi_remove_confirm_{adm}"))
        markup.add(ibtn("Back", callback_data="admin_menu_multiadmin", style="danger", custom_emoji_id=get_emj_id("wrong")))
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="HTML")

    elif data.startswith("adm_multi_remove_confirm_"):
        target_adm = int(data.replace("adm_multi_remove_confirm_", ""))
        db_admins = db.setdefault("admins", [SUPERADMIN_ID])
        if target_adm in db_admins:
            db_admins.remove(target_adm)
            save_db(db)
            bot.answer_callback_query(call.id, f"Admin ID {target_adm} removed!")
        render_multiadmin_menu(call.message.chat.id, call.message.message_id)

    # Profile interactions
    elif data.startswith("adm_usr_"):
        parts = data.split("_")
        action = parts[2]
        target_id = parts[3]
        
        if action == "addmoney":
            user_states[user_id] = f"adm_state_addmoney_{target_id}"
            bot.send_message(call.message.chat.id, f"Please enter the Tk amount to <b>ADD</b> to User <code>{target_id}</code>:", parse_mode="HTML")
        elif action == "dedmoney":
            user_states[user_id] = f"adm_state_dedmoney_{target_id}"
            bot.send_message(call.message.chat.id, f"Please enter the Tk amount to <b>DEDUCT</b> from User <code>{target_id}</code>:", parse_mode="HTML")
        elif action == "addplan":
            user_states[user_id] = f"adm_state_addplan_{target_id}"
            bot.send_message(call.message.chat.id, f"Enter validity duration in **DAYS** to grant plan to User <code>{target_id}</code>:", parse_mode="HTML")
        elif action == "remplan":
            target_user = get_user(target_id, db)
            target_user["plan"] = "NONE"
            target_user["plan_expiry"] = None
            save_db(db)
            
            limit = target_user.get("slot_limit", 2)
            for i in range(1, limit + 1):
                stop_bot_process(target_id, f"slot{i}")
                
            bot.send_message(call.message.chat.id, f"Plan successfully canceled for user {target_id}.", parse_mode="HTML")
            try: bot.send_message(target_id, "Your active subscription plan has been canceled by the Admin.")
            except: pass
            manage_user_profile(call.message.chat.id, target_id, edit_message_id=call.message.message_id)
            
        elif action == "ban":
            banned_users = db.setdefault("banned_users", [])
            target_str = str(target_id)
            if target_str in banned_users:
                banned_users.remove(target_str)
                bot.send_message(call.message.chat.id, f"User {target_id} has been unbanned.", parse_mode="HTML")
                try: bot.send_message(target_id, "Your account has been unbanned by the Admin!")
                except: pass
            else:
                banned_users.append(target_str)
                stop_bot_process(target_id, "slot1")
                stop_bot_process(target_id, "slot2")
                bot.send_message(call.message.chat.id, f"User {target_id} has been banned.", parse_mode="HTML")
                try: bot.send_message(target_id, "Your account has been banned by the Admin.")
                except: pass
            save_db(db)
            manage_user_profile(call.message.chat.id, target_id, edit_message_id=call.message.message_id)
            
        elif action == "limit":
            user_states[user_id] = f"adm_state_setlimit_{target_id}"
            bot.send_message(call.message.chat.id, f"Please enter new slot limit for User ID <code>{target_id}</code>:", parse_mode="HTML")

        elif action == "msg":
            user_states[user_id] = f"adm_usr_sendalert_{target_id}"
            bot.send_message(call.message.chat.id, f"Send private message alert to User <code>{target_id}</code>:")

        elif action == "files":
            target_user = get_user(target_id, db)
            limit = target_user.get("slot_limit", 2)
            
            text = f"Explore Hosted Project Files for User: <code>{target_id}</code>\n\nSelect slot directory:"
            markup = InlineKeyboardMarkup(row_width=2)
            for i in range(1, limit + 1):
                slot_name = f"slot{i}"
                markup.add(ibtn(f"Slot {i} Explorer", callback_data=f"adm_usr_slotexplore_{target_id}_{slot_name}"))
            markup.add(ibtn("Back to Profile", callback_data=f"adm_usr_backtoprofile_{target_id}"))
            bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="HTML")

        elif action == "backtoprofile":
            manage_user_profile(call.message.chat.id, target_id, edit_message_id=call.message.message_id)

        elif action == "slotexplore":
            slot_name = parts[4]
            slot_dir = f"hosted_bots/{target_id}/{slot_name}"
            
            file_tree_txt = f"Directory tree: {slot_name.upper()} ({target_id}):\n\n"
            if not os.path.exists(slot_dir):
                file_tree_txt += "Empty Slot. No files found."
            else:
                files_found = []
                for root, dirs, filenames in os.walk(slot_dir):
                    for filename in filenames:
                        rel_path = os.path.relpath(os.path.join(root, filename), slot_dir)
                        files_found.append(rel_path)
                
                if not files_found:
                    file_tree_txt += "Empty directory."
                else:
                    for idx, relative_f in enumerate(files_found, 1):
                        file_tree_txt += f"📄 <code>{relative_f}</code>\n"
                    
                    file_tree_txt += (
                        f"\nTo view file contents, type command:\n"
                        f"<code>/viewfile {target_id} {slot_name} relative_file_path</code>"
                    )
            
            markup = InlineKeyboardMarkup()
            btn_zip = ibtn("Get Slot Backup ZIP", callback_data=f"adm_usr_getzip_{target_id}_{slot_name}")
            btn_back = ibtn("Back", callback_data=f"adm_usr_files_{target_id}", style="danger", custom_emoji_id=get_emj_id("wrong"))
            markup.add(btn_zip)
            markup.add(btn_back)
            bot.edit_message_text(file_tree_txt, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="HTML")

        elif action == "getzip":
            slot_name = parts[4]
            slot_dir = f"hosted_bots/{target_id}/{slot_name}"
            if os.path.exists(slot_dir):
                zip_archive_path = f"hosted_bots/{target_id}/{slot_name}_admin_view"
                shutil.make_archive(zip_archive_path, 'zip', slot_dir)
                
                with open(f"{zip_archive_path}.zip", 'rb') as doc:
                    bot.send_document(call.message.chat.id, doc, caption=f"File Explorer ZIP: User `{target_id}` Slot `{slot_name}`")
                os.remove(f"{zip_archive_path}.zip")
            else:
                bot.send_message(call.message.chat.id, "❌ No slot folder files are found to archive.")


# ==================================================
# --- সাধারণ টেক্সট মেসেজ ও বাটন হ্যান্ডলার ---
# ==================================================
@bot.message_handler(func=lambda message: message.text is not None)
def handle_all_text_messages(message):
    if check_security(message): return
    
    user_id = message.from_user.id
    
    # অ্যাডমিন প্যানেল ক্লিক হ্যান্ডেল
    if "Admin Panel" in message.text:
        if is_admin(user_id):
            show_admin_dashboard(message.chat.id)
        return

    # সাধারণ কীবোর্ড বাটন প্রসেস
    if "Deploy Bot" in message.text:
        deploy_slot_select(message)
    elif "Status & Manage" in message.text:
        show_status(message)
    elif "Products / Plans" in message.text:
        show_products_text(message)
    elif "Deposit & Wallet" in message.text:
        show_wallet_text(message)
    elif "Support" in message.text:
        show_support_info(message)

# অ্যাডমিন স্ল্যাশ কমান্ড ভিউয়ার
@bot.message_handler(commands=['admin', 'panel'])
def admin_panel_command_click(message):
    if is_admin(message.from_user.id):
        show_admin_dashboard(message.chat.id)

# বট স্টার্টআপ
if __name__ == "__main__":
    # --- Start Flask Server in Background ---
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()

    print("Bot Hosting Bot has successfully started with Premium Custom Emojis, and all global setting and HTML glitches resolved...")
    bot.infinity_polling()