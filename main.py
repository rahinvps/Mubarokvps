import os
import threading
from flask import Flask

# --- FLASK SERVER SETUP FOR RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is successfully running on Render! Rahin File Host"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = threading.Thread(target=run_server)
    t.daemon = True
    t.start()
    print("Flask Keep-Alive server started.")
# --- End Flask Keep Alive ---

import telebot
import subprocess
import zipfile
import tempfile
import shutil
from telebot import types
import time
from datetime import datetime, timedelta
import psutil
import json
import logging
import signal
import re
import sys
import atexit
import hashlib
import mimetypes
import struct
import psycopg2  # Supabase Postgres Connection
import ast       # Added for dynamic auto-dependency parser

# --- Configuration ---
TOKEN = '8957896268:AAFGTYeNWNp9oVTr4iD-caZsDIP-Bkocpbs' 
OWNER_ID = 5409553122
ADMIN_ID = 5409553122
YOUR_USERNAME = '@rahi455'
UPDATE_CHANNEL = 'https://t.me/rmmethodzone'

# --- SUPABASE POSTGRESQL CONNECTION ---
DB_URI = "postgresql://postgres:Rahin12@@##@db.gcgxxhwkehwtdoeilbah.supabase.co:5432/postgres"

# Folder setup - using absolute paths
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')

# File upload limits
OWNER_LIMIT = float('inf')
ADMIN_LIMIT = float('inf')

# Create necessary directories
os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
os.makedirs(IROTECH_DIR, exist_ok=True)

# Initialize bot
bot = telebot.TeleBot(TOKEN)

# --- Clean Active Webhook Conflicts ---
try:
    bot.remove_webhook()
except Exception as e:
    print(f"Webhook cleanup note: {e}")

# --- PostgreSQL Connection & Table Initializer ---
def get_db_connection():
    return psycopg2.connect(DB_URI)

def init_db():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Create Tables
        cur.execute("""
        CREATE TABLE IF NOT EXISTS active_users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            join_date TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS admins (
            admin_id BIGINT PRIMARY KEY
        );
        CREATE TABLE IF NOT EXISTS balances (
            user_id BIGINT PRIMARY KEY,
            balance DOUBLE PRECISION DEFAULT 0.0
        );
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id BIGINT PRIMARY KEY,
            expiry TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS user_files (
            user_id BIGINT,
            file_name TEXT,
            file_type TEXT,
            upload_time TIMESTAMP,
            PRIMARY KEY (user_id, file_name)
        );
        CREATE TABLE IF NOT EXISTS packages (
            id TEXT PRIMARY KEY,
            name TEXT,
            days INT,
            price DOUBLE PRECISION,
            purchase_limit INT DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS deposits (
            id TEXT PRIMARY KEY,
            user_id BIGINT,
            amount DOUBLE PRECISION,
            status TEXT,
            screenshot_file_id TEXT,
            recipient_number TEXT,
            send_time TEXT,
            method TEXT
        );
        CREATE TABLE IF NOT EXISTS purchase_counts (
            user_id BIGINT,
            pack_id TEXT,
            count INT,
            PRIMARY KEY (user_id, pack_id)
        );
        CREATE TABLE IF NOT EXISTS user_directory_files (
            user_id BIGINT,
            file_path TEXT,
            file_data BYTEA,
            PRIMARY KEY (user_id, file_path)
        );
        """)
        conn.commit()
        
        # Seed default packages if table is empty
        cur.execute("SELECT COUNT(*) FROM packages;")
        if cur.fetchone()[0] == 0:
            cur.execute("""
            INSERT INTO packages (id, name, days, price, purchase_limit) VALUES
            ('1', '1 Day VPS Plan', 1, 15.0, 0),
            ('2', '7 Days VPS Plan', 7, 49.0, 0),
            ('3', '30 Days VPS Plan', 30, 149.0, 0);
            """)
            conn.commit()
            
        # Seed default settings if empty
        cur.execute("SELECT COUNT(*) FROM settings;")
        if cur.fetchone()[0] == 0:
            cur.execute("""
            INSERT INTO settings (key, value) VALUES
            ('non_sub_limit', '0'),
            ('sub_limit', '3'),
            ('sales_status', 'ON'),
            ('recharge_status', 'ON');
            """)
            conn.commit()
            
        cur.close()
    except Exception as e:
        print(f"Error initializing Supabase DB: {e}")
    finally:
        if conn:
            conn.close()

# --- Cache Structures ---
bot_scripts = {}
user_subscriptions = {}
user_balances = {}
temp_recharges = {}
temp_deploy_name = {}
user_files = {}
active_users = set()
admin_ids = {ADMIN_ID, OWNER_ID}
bot_locked = False
pending_broadcasts = {} 

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Command Button Layouts ---
COMMAND_BUTTONS_LAYOUT_USER_SPEC = [
    ["🛍️ Products", "💵 Balance"],
    ["💵 Recharge", "🚀 Deploy Bot"],
    ["🤖 My Bot", "⚡ Bot Speed"],
    ["📊 Statistics", "📞 Help & Support"]
]
ADMIN_COMMAND_BUTTONS_LAYOUT_USER_SPEC = [
    ["🛍️ Products", "💵 Balance"],
    ["💵 Recharge", "🚀 Deploy Bot"],
    ["🤖 My Bot", "⚡ Bot Speed"],
    ["📊 Statistics", "👑 Admin Panel"],
    ["📞 Help & Support"]
]

# --- Helper Functions ---
def get_user_folder(user_id):
    folder = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
    os.makedirs(folder, exist_ok=True)
    return folder

def is_user_admin(user_id):
    if not user_id:
        return False
    try:
        uid_int = int(user_id)
    except ValueError:
        return False
    return uid_int in admin_ids or uid_int == OWNER_ID or uid_int == ADMIN_ID

def calculate_fair_expiry(days, current_expiry=None):
    start_date = datetime.now()
    if current_expiry and current_expiry > start_date:
        start_date = current_expiry
    new_expiry = (start_date + timedelta(days=days)).replace(hour=23, minute=59, second=59, microsecond=0)
    return new_expiry

def get_user_file_limit(user_id):
    if user_id == OWNER_ID or is_user_admin(user_id): 
        return OWNER_LIMIT
    if has_active_subscription(user_id):
        return int(get_setting("sub_limit", "3"))
    return int(get_setting("non_sub_limit", "0"))

def get_user_file_count(user_id):
    return len(user_files.get(user_id, []))

def has_active_subscription(user_id):
    if is_user_admin(user_id) or user_id == OWNER_ID:
        return True
    if user_id in user_subscriptions:
        expiry = user_subscriptions[user_id].get('expiry')
        if expiry and expiry > datetime.now():
            return True
    return False

def get_active_bot_count(user_id):
    count = 0
    for script_key, script_info in bot_scripts.items():
        if script_info.get('script_owner_id') == user_id:
            if is_bot_running(user_id, script_info['file_name']):
                count += 1
    return count

def get_active_bot_limit(user_id):
    if is_user_admin(user_id) or user_id == OWNER_ID:
        return float('inf') 
    return 3 

# --- Dynamic Auto-Dependency Installer Helpers ---
def auto_install_python_deps(file_path, user_folder, user_id):
    """Parses Python file imports and automatically runs pip install for missing packages."""
    imports = set()
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports.add(name.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
    except Exception:
        # Fallback to Regex parser if AST fails due to syntax error
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    match1 = re.match(r'^\s*import\s+([a-zA-Z0-9_]+)', line)
                    match2 = re.match(r'^\s*from\s+([a-zA-Z0-9_]+)', line)
                    if match1:
                        imports.add(match1.group(1))
                    elif match2:
                        imports.add(match2.group(1))
        except Exception:
            pass

    # Built-in Python Standard Libraries to avoid trying to install
    STDLIB_MODULES = {
        'os', 'sys', 'time', 're', 'json', 'math', 'random', 'datetime', 'threading',
        'subprocess', 'shutil', 'tempfile', 'zipfile', 'logging', 'signal', 'struct',
        'hashlib', 'mimetypes', 'socket', 'urllib', 'collections', 'itertools', 'functools',
        'traceback', 'asyncio', 'select', 'platform', 'uuid', 'base64', 'csv', 'ast',
        'typing', 'pathlib', 'atexit', 'inspect', 'copy', 'glob', 'pickle', 'weakref',
        'gc', 'abc', 'contextlib', 'argparse', 'importlib', 'xml', 'html', 'http', 'ctypes',
        'trace', 'string', 'io', 'errno', 'stat', 'fnmatch', 'warnings', 'sqlite3'
    }

    # Import Name to PyPI Package Name Mapping
    MODULE_MAPPING = {
        'telebot': 'pyTelegramBotAPI',
        'telegram': 'python-telegram-bot',
        'PIL': 'Pillow',
        'bs4': 'beautifulsoup4',
        'pg': 'postgresql',
        'mysql': 'mysql-connector-python'
    }

    packages_to_install = []
    for imp in imports:
        if imp in STDLIB_MODULES:
            continue
        pkg = MODULE_MAPPING.get(imp, imp)
        if pkg:
            packages_to_install.append(pkg)

    if packages_to_install:
        logger.info(f"Auto-installing detected Python packages for User {user_id}: {packages_to_install}")
        try:
            bot.send_message(user_id, f"🔄 *Auto-installing required packages:* `{', '.join(packages_to_install)}`...", parse_mode='Markdown')
        except Exception:
            pass

        for pkg in packages_to_install:
            try:
                subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', pkg],
                    capture_output=True, text=True, check=True, timeout=60
                )
            except Exception as e:
                logger.error(f"Failed to auto-install package {pkg}: {e}")

def auto_install_js_deps(file_path, user_folder, user_id):
    """Parses Node JS file requirements and automatically runs npm install for missing packages."""
    imports = set()
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        req_matches = re.findall(r'require\s*\(\s*[\'"]([@a-zA-Z0-9_\-\/]+)[\'"]\s*\)', content)
        import_matches = re.findall(r'from\s+[\'"]([@a-zA-Z0-9_\-\/]+)[\'"]', content)
        import_fn_matches = re.findall(r'import\s*\(\s*[\'"]([@a-zA-Z0-9_\-\/]+)[\'"]\s*\)', content)
        
        for pkg in req_matches + import_matches + import_fn_matches:
            if pkg.startswith('@'):
                parts = pkg.split('/')
                if len(parts) >= 2:
                    imports.add(f"{parts[0]}/{parts[1]}")
            else:
                imports.add(pkg.split('/')[0])
    except Exception:
        pass

    NODE_BUILTINS = {
        'fs', 'path', 'http', 'https', 'crypto', 'os', 'child_process', 'events',
        'util', 'stream', 'dns', 'net', 'url', 'querystring', 'zlib', 'assert',
        'buffer', 'cluster', 'constants', 'readline', 'repl', 'tls', 'vm'
    }

    packages_to_install = [pkg for pkg in imports if pkg not in NODE_BUILTINS]

    if packages_to_install:
        logger.info(f"Auto-installing detected JS packages for User {user_id}: {packages_to_install}")
        try:
            bot.send_message(user_id, f"🔄 *Auto-installing required npm packages:* `{', '.join(packages_to_install)}`...", parse_mode='Markdown')
        except Exception:
            pass

        for pkg in packages_to_install:
            try:
                subprocess.run(
                    ['npm', 'install', pkg],
                    cwd=user_folder, capture_output=True, text=True, check=True, timeout=120
                )
            except Exception as e:
                logger.error(f"Failed to auto-install npm package {pkg}: {e}")

# --- Database Persistent File Sync System ---
def save_user_file(user_id, file_name, file_type):
    """Saves user file metadata to database and updates local memory cache."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO user_files (user_id, file_name, file_type, upload_time)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id, file_name) 
            DO UPDATE SET file_type = EXCLUDED.file_type, upload_time = EXCLUDED.upload_time;
        """, (user_id, file_name, file_type, datetime.now()))
        conn.commit()
        cur.close()
    except Exception as e:
        logger.error(f"Error in save_user_file database query: {e}")
    finally:
        if conn:
            conn.close()
            
    # Update local memory cache
    if user_id not in user_files:
        user_files[user_id] = []
    user_files[user_id] = [f for f in user_files[user_id] if f[0] != file_name]
    user_files[user_id].append((file_name, file_type))

def save_file_to_db(user_id, file_path_on_disk):
    user_folder = get_user_folder(user_id)
    relative_path = os.path.relpath(file_path_on_disk, user_folder)
    conn = None
    try:
        if not os.path.exists(file_path_on_disk) or os.path.isdir(file_path_on_disk):
            return
        with open(file_path_on_disk, 'rb') as f:
            file_data = f.read()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO user_directory_files (user_id, file_path, file_data)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, file_path) DO UPDATE SET file_data = EXCLUDED.file_data;
        """, (user_id, relative_path, psycopg2.Binary(file_data)))
        conn.commit()
        cur.close()
    except Exception as e:
        logger.error(f"Error saving file {relative_path} to Supabase: {e}")
    finally:
        if conn:
            conn.close()

def save_user_folder_to_db(user_id):
    user_folder = get_user_folder(user_id)
    for root, dirs, files in os.walk(user_folder):
        for file in files:
            file_path = os.path.join(root, file)
            save_file_to_db(user_id, file_path)

def delete_file_from_db(user_id, relative_path):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM user_directory_files WHERE user_id = %s AND file_path = %s;", (user_id, relative_path))
        conn.commit()
        cur.close()
    except Exception as e:
        logger.error(f"Error deleting file {relative_path} from Supabase: {e}")
    finally:
        if conn:
            conn.close()

def delete_all_user_files_from_db(user_id):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM user_directory_files WHERE user_id = %s;", (user_id,))
        conn.commit()
        cur.close()
    except Exception as e:
        logger.error(f"Error deleting all files of user {user_id} from Supabase: {e}")
    finally:
        if conn:
            conn.close()

def restore_all_files_from_db():
    logger.info("Restoring persistent user directory files from Supabase PostgreSQL...")
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT user_id, file_path, file_data FROM user_directory_files;")
        rows = cur.fetchall()
        for row in rows:
            user_id, file_path, file_data = row
            user_folder = get_user_folder(user_id)
            dest_path = os.path.join(user_folder, file_path)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, 'wb') as f:
                f.write(bytes(file_data) if isinstance(file_data, memoryview) else file_data)
        cur.close()
        logger.info("All user directory files successfully restored on local disk.")
    except Exception as e:
        logger.error(f"Error restoring files from Supabase: {e}")
    finally:
        if conn:
            conn.close()

# --- Database Sync Helpers ---
def load_data():
    logger.info("Syncing PostgreSQL database...")
    global active_users, admin_ids, user_balances, user_subscriptions, user_files
    init_db()  
    
    # Restore persistent deployment files to local filesystem
    restore_all_files_from_db()
    
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Load active users
        cur.execute("SELECT user_id FROM active_users;")
        active_users = set(int(row[0]) for row in cur.fetchall())
        
        # Load admins
        cur.execute("SELECT admin_id FROM admins;")
        admin_ids = set(int(row[0]) for row in cur.fetchall())
        admin_ids.add(OWNER_ID)
        admin_ids.add(ADMIN_ID)
        
        # Load balances
        cur.execute("SELECT user_id, balance FROM balances;")
        user_balances = {int(row[0]): float(row[1]) for row in cur.fetchall()}
        
        # Load subscriptions
        cur.execute("SELECT user_id, expiry FROM subscriptions;")
        user_subscriptions = {}
        for row in cur.fetchall():
            uid = int(row[0])
            expiry = row[1]
            if expiry:
                user_subscriptions[uid] = {'expiry': expiry}
                
        # Load user_files
        cur.execute("SELECT user_id, file_name, file_type FROM user_files;")
        user_files = {}
        for row in cur.fetchall():
            uid = int(row[0])
            file_name = row[1]
            file_type = row[2]
            if uid not in user_files:
                user_files[uid] = []
            user_files[uid].append((file_name, file_type))
            
        cur.close()
        logger.info("Database loaded successfully from Supabase.")
    except Exception as e:
        logger.error(f"❌ Error loading database from Supabase: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()

load_data()

def get_all_packages():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, name, days, price, purchase_limit FROM packages;")
        rows = cur.fetchall()
        packs = {}
        for r in rows:
            packs[r[0]] = {
                "name": r[1],
                "days": r[2],
                "price": float(r[3]),
                "purchase_limit": r[4]
            }
        cur.close()
        return packs
    except Exception as e:
        logger.error(f"Error in get_all_packages: {e}")
        return {}
    finally:
        if conn:
            conn.close()

def remove_user_file_db(user_id, file_name):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM user_files WHERE user_id = %s AND file_name = %s;", (user_id, file_name))
        conn.commit()
        cur.close()
    except Exception as e:
        logger.error(f"Error in remove_user_file_db: {e}")
    finally:
        if conn:
            conn.close()
            
    if user_id in user_files:
        user_files[user_id] = [f for f in user_files[user_id] if f[0] != file_name]
        if not user_files[user_id]: del user_files[user_id]

def add_active_user(user_id, username="N/A"):
    active_users.add(user_id)
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO active_users (user_id, username, join_date)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username;
        """, (user_id, username, datetime.now()))
        conn.commit()
        cur.close()
    except Exception as e:
        logger.error(f"Error in add_active_user: {e}")
    finally:
        if conn:
            conn.close()

def save_subscription(user_id, expiry):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO subscriptions (user_id, expiry)
            VALUES (%s, %s)
            ON CONFLICT (user_id) DO UPDATE SET expiry = EXCLUDED.expiry;
        """, (user_id, expiry))
        conn.commit()
        cur.close()
    except Exception as e:
        logger.error(f"Error in save_subscription: {e}")
    finally:
        if conn:
            conn.close()
    user_subscriptions[user_id] = {'expiry': expiry}

def remove_subscription_db(user_id):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM subscriptions WHERE user_id = %s;", (user_id,))
        conn.commit()
        cur.close()
    except Exception as e:
        logger.error(f"Error in remove_subscription_db: {e}")
    finally:
        if conn:
            conn.close()
    if user_id in user_subscriptions: del user_subscriptions[user_id]

def add_admin_db(admin_id):
    admin_ids.add(admin_id)
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO admins (admin_id) VALUES (%s) ON CONFLICT (admin_id) DO NOTHING;", (admin_id,))
        conn.commit()
        cur.close()
    except Exception as e:
        logger.error(f"Error in add_admin_db: {e}")
    finally:
        if conn:
            conn.close()

def remove_admin_db(admin_id):
    if admin_id in [OWNER_ID, ADMIN_ID]:
        return False
    admin_ids.discard(admin_id)
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM admins WHERE admin_id = %s;", (admin_id,))
        conn.commit()
        cur.close()
    except Exception as e:
        logger.error(f"Error in remove_admin_db: {e}")
    finally:
        if conn:
            conn.close()
    return True

def get_setting(key, default_value):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = %s;", (key,))
        row = cur.fetchone()
        cur.close()
        if row:
            return row[0]
    except Exception as e:
        logger.error(f"Error in get_setting: {e}")
    finally:
        if conn:
            conn.close()
    return str(default_value)

def set_setting(key, value):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO settings (key, value)
            VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
        """, (key, str(value)))
        conn.commit()
        cur.close()
    except Exception as e:
        logger.error(f"Error in set_setting: {e}")
    finally:
        if conn:
            conn.close()

def get_balance(user_id):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT balance FROM balances WHERE user_id = %s;", (user_id,))
        row = cur.fetchone()
        cur.close()
        if row:
            return float(row[0])
    except Exception as e:
        logger.error(f"Error in get_balance: {e}")
    finally:
        if conn:
            conn.close()
    return 0.0

def set_balance(user_id, amount):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO balances (user_id, balance)
            VALUES (%s, %s)
            ON CONFLICT (user_id) DO UPDATE SET balance = EXCLUDED.balance;
        """, (user_id, float(amount)))
        conn.commit()
        cur.close()
    except Exception as e:
        logger.error(f"Error in set_balance: {e}")
    finally:
        if conn:
            conn.close()
    user_balances[user_id] = float(amount)

# --- Additional Supabase DB Helper Functions ---
def get_purchase_count(user_id, pack_id):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT count FROM purchase_counts WHERE user_id = %s AND pack_id = %s;", (user_id, pack_id))
        row = cur.fetchone()
        cur.close()
        if row:
            return int(row[0])
    except Exception as e:
        logger.error(f"Error in get_purchase_count: {e}")
    finally:
        if conn:
            conn.close()
    return 0

def increment_purchase_count(user_id, pack_id):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO purchase_counts (user_id, pack_id, count)
            VALUES (%s, %s, 1)
            ON CONFLICT (user_id, pack_id) DO UPDATE SET count = purchase_counts.count + 1;
        """, (user_id, pack_id))
        conn.commit()
        cur.close()
    except Exception as e:
        logger.error(f"Error in increment_purchase_count: {e}")
    finally:
        if conn:
            conn.close()

def save_deposit(deposit_id, user_id, amount, status, screenshot_file_id, recipient, send_time, method):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO deposits (id, user_id, amount, status, screenshot_file_id, recipient_number, send_time, method)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """, (deposit_id, user_id, amount, status, screenshot_file_id, recipient, send_time, method))
        conn.commit()
        cur.close()
    except Exception as e:
        logger.error(f"Error in save_deposit: {e}")
    finally:
        if conn:
            conn.close()

def get_deposit(deposit_id):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT user_id, amount, status, screenshot_file_id, recipient_number, send_time, method FROM deposits WHERE id = %s;", (deposit_id,))
        row = cur.fetchone()
        cur.close()
        if row:
            return {
                "user_id": row[0],
                "amount": row[1],
                "status": row[2],
                "screenshot_file_id": row[3],
                "recipient_number": row[4],
                "send_time": row[5],
                "method": row[6]
            }
    except Exception as e:
        logger.error(f"Error in get_deposit: {e}")
    finally:
        if conn:
            conn.close()
    return None

def update_deposit_status(deposit_id, status):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE deposits SET status = %s WHERE id = %s;", (status, deposit_id))
        conn.commit()
        cur.close()
    except Exception as e:
        logger.error(f"Error in update_deposit_status: {e}")
    finally:
        if conn:
            conn.close()

def get_user_info(user_id):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT username, join_date FROM active_users WHERE user_id = %s;", (user_id,))
        row = cur.fetchone()
        cur.close()
        if row:
            return {
                "username": row[0] or "N/A",
                "join_date": row[1]
            }
    except Exception as e:
        logger.error(f"Error in get_user_info: {e}")
    finally:
        if conn:
            conn.close()
    return {"username": "N/A", "join_date": None}

def get_file_info(user_id, file_name):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT file_type, upload_time FROM user_files WHERE user_id = %s AND file_name = %s;", (user_id, file_name))
        row = cur.fetchone()
        cur.close()
        if row:
            return {
                "type": row[0],
                "upload_time": row[1]
            }
    except Exception as e:
        logger.error(f"Error in get_file_info: {e}")
    finally:
        if conn:
            conn.close()
    return None

def update_package(pack_id, field, value):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(f"UPDATE packages SET {field} = %s WHERE id = %s;", (value, pack_id))
        conn.commit()
        cur.close()
    except Exception as e:
        logger.error(f"Error in update_package: {e}")
    finally:
        if conn:
            conn.close()

def add_package(pack_id, name, days, price, purchase_limit=0):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO packages (id, name, days, price, purchase_limit)
            VALUES (%s, %s, %s, %s, %s);
        """, (pack_id, name, days, price, purchase_limit))
        conn.commit()
        cur.close()
    except Exception as e:
        logger.error(f"Error in add_package: {e}")
    finally:
        if conn:
            conn.close()

# --- Intercept menu interactions ---
def check_menu_intercept(message):
    if message.text:
        cleaned_text = message.text.strip()
        if cleaned_text in BUTTON_TEXT_TO_LOGIC or cleaned_text.startswith('/'):
            user_id = message.from_user.id
            if user_id in temp_recharges:
                del temp_recharges[user_id]
            if user_id in temp_deploy_name:
                del temp_deploy_name[user_id]
            
            if cleaned_text.startswith('/'):
                if cleaned_text == '/start':
                    _logic_send_welcome(message)
                elif cleaned_text == '/uploadfile':
                    _logic_upload_file(message, sender_id=message.from_user.id)
                elif cleaned_text == '/checkfiles':
                    _logic_check_files(message, sender_id=message.from_user.id)
                elif cleaned_text == '/botspeed':
                    _logic_bot_speed(message, sender_id=message.from_user.id)
                elif cleaned_text == '/sendcommand':
                    _logic_send_command(message)
                elif cleaned_text == '/contactowner':
                    _logic_contact_owner(message)
                elif cleaned_text == '/subscriptions':
                    _logic_subscriptions_panel(message)
                elif cleaned_text == '/statistics':
                    _logic_statistics(message, sender_id=message.from_user.id)
                elif cleaned_text == '/broadcast':
                    _logic_broadcast_init(message, sender_id=message.from_user.id)
                elif cleaned_text == '/lockbot':
                    _logic_toggle_lock_bot(message)
                elif cleaned_text == '/adminpanel':
                    _logic_admin_panel(message)
                elif cleaned_text == '/runningallcode':
                    _logic_run_all_scripts(message)
                elif cleaned_text == '/ping':
                    ping(message)
                elif cleaned_text == '/restart':
                    command_restart_main(message)
            else:
                logic_func = BUTTON_TEXT_TO_LOGIC.get(cleaned_text)
                if logic_func:
                    logic_func(message)
            return True
    return False

# --- Core Bot Engine Mechanics ---
def is_bot_running(user_id, file_name):
    script_key = f"{user_id}_{file_name}"
    if script_key in bot_scripts:
        process_info = bot_scripts[script_key]
        process = process_info.get('process')
        if process and process.poll() is None:
            return True
        try:
            del bot_scripts[script_key]
        except KeyError:
            pass
    return False

def kill_process_tree(process_info):
    process = process_info.get('process')
    if not process:
        return
    try:
        parent = psutil.Process(process.pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()
    except Exception as e:
        logger.error(f"Error killing process tree: {e}")
        try:
            process.terminate()
        except Exception:
            pass

def run_script(file_path, user_id, user_folder, file_name, message_obj):
    # Auto-install missing Python packages before starting
    auto_install_python_deps(file_path, user_folder, user_id)

    script_key = f"{user_id}_{file_name}"
    log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
    
    if os.path.exists(log_path):
        try: os.remove(log_path)
        except Exception: pass
        
    try:
        log_file = open(log_path, 'w', encoding='utf-8', errors='ignore')
        # Added -u flag to execute Python scripts completely unbuffered for Realtime Logs
        process = subprocess.Popen(
            [sys.executable, '-u', file_path],
            stdout=log_file,
            stderr=log_file,
            stdin=subprocess.PIPE,
            cwd=user_folder,
            text=True,
            bufsize=1
        )
        bot_scripts[script_key] = {
            'process': process,
            'script_owner_id': user_id,
            'file_name': file_name,
            'start_time': datetime.now(),
            'log_file': log_file
        }
        logger.info(f"Started Python script {file_name} for user {user_id}")
        
        # Deployment DONE Status Alert
        time.sleep(1.5)
        if is_bot_running(user_id, file_name):
            try:
                bot.send_message(user_id, f"🎉 *Deployment Status: DONE!* ✅\n\n🚀 Bot `{file_name}` is online and running successfully!", parse_mode='Markdown')
            except Exception: pass
            
    except Exception as e:
        logger.error(f"Error starting script {file_name}: {e}")
        try:
            bot.send_message(user_id, f"❌ Failed to start script `{file_name}`. Error: {e}", parse_mode='Markdown')
        except Exception: pass

def run_js_script(file_path, user_id, user_folder, file_name, message_obj):
    # Auto-install missing JS npm packages before starting
    auto_install_js_deps(file_path, user_folder, user_id)

    script_key = f"{user_id}_{file_name}"
    log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
    
    if os.path.exists(log_path):
        try: os.remove(log_path)
        except Exception: pass
        
    try:
        log_file = open(log_path, 'w', encoding='utf-8', errors='ignore')
        process = subprocess.Popen(
            ['node', file_path],
            stdout=log_file,
            stderr=log_file,
            stdin=subprocess.PIPE,
            cwd=user_folder,
            text=True,
            bufsize=1
        )
        bot_scripts[script_key] = {
            'process': process,
            'script_owner_id': user_id,
            'file_name': file_name,
            'start_time': datetime.now(),
            'log_file': log_file
        }
        logger.info(f"Started JS script {file_name} for user {user_id}")
        
        # Deployment DONE Status Alert
        time.sleep(1.5)
        if is_bot_running(user_id, file_name):
            try:
                bot.send_message(user_id, f"🎉 *Deployment Status: DONE!* ✅\n\n🚀 Bot `{file_name}` is online and running successfully!", parse_mode='Markdown')
            except Exception: pass
            
    except Exception as e:
        logger.error(f"Error starting JS script {file_name}: {e}")
        try:
            bot.send_message(user_id, f"❌ Failed to start JS script `{file_name}`. Error: {e}", parse_mode='Markdown')
        except Exception: pass

# --- Menus & Keyboards Creators ---
def create_reply_keyboard_main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    btn_products = types.KeyboardButton("🛍️ Products")
    btn_balance = types.KeyboardButton("💵 Balance")
    btn_recharge = types.KeyboardButton("💵 Recharge")
    btn_deploy = types.KeyboardButton("🚀 Deploy Bot")
    btn_my_bot = types.KeyboardButton("🤖 My Bot")
    btn_speed = types.KeyboardButton("⚡ Bot Speed")
    btn_stats = types.KeyboardButton("📊 Statistics")
    btn_support = types.KeyboardButton("📞 Help & Support")
    
    markup.row(btn_products, btn_balance)
    markup.row(btn_recharge, btn_deploy)
    markup.row(btn_my_bot, btn_speed)
    
    if is_user_admin(user_id):
        btn_admin = types.KeyboardButton("👑 Admin Panel")
        markup.row(btn_stats, btn_admin)
        markup.row(btn_support)
    else:
        markup.row(btn_stats, btn_support)
        
    return markup

def create_send_command_menu():
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🔵 Send to Running Script", callback_data="send_to_process"),
        types.InlineKeyboardButton("📜 View All Logs", callback_data="view_all_logs")
    )
    return markup

def create_subscription_menu():
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("➕ Add Sub", callback_data="add_subscription"),
        types.InlineKeyboardButton("➖ Remove Sub", callback_data="remove_subscription")
    )
    markup.row(
        types.InlineKeyboardButton("🔍 Check Sub Status", callback_data="check_subscription"),
        types.InlineKeyboardButton("🔵 Admin Panel", callback_data="admin_panel")
    )
    return markup

def create_admin_panel():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton("👥 Manage Users", callback_data="admin_manage_user"),
        types.InlineKeyboardButton("📦 Edit Packages", callback_data="admin_edit_packages")
    )
    markup.row(
        types.InlineKeyboardButton("🟢 Running Bots", callback_data="admin_running_bots"),
        types.InlineKeyboardButton("🚀 Run All User Scripts", callback_data="run_all_scripts")
    )
    
    sales_status = get_setting("sales_status", "ON")
    sales_btn_text = "🔴 Turn Sales OFF" if sales_status == "ON" else "🟢 Turn Sales ON"
    
    recharge_status = get_setting("recharge_status", "ON")
    recharge_btn_text = "🔴 Turn Recharge OFF" if recharge_status == "ON" else "🟢 Turn Recharge ON"
    
    markup.row(
        types.InlineKeyboardButton(sales_btn_text, callback_data="admin_toggle_sales"),
        types.InlineKeyboardButton(recharge_btn_text, callback_data="admin_toggle_recharge")
    )
    markup.row(
        types.InlineKeyboardButton("📢 Broadcast Msg", callback_data="broadcast"),
        types.InlineKeyboardButton("🔑 Manage Admins", callback_data="list_admins")
    )
    markup.row(
        types.InlineKeyboardButton("🟢 Add Admin", callback_data="add_admin"),
        types.InlineKeyboardButton("🔴 Remove Admin", callback_data="remove_admin")
    )
    markup.row(
        types.InlineKeyboardButton("🔵 Back to Main", callback_data="back_to_main")
    )
    return markup

def create_control_buttons(user_id, file_name, is_running, viewer_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if is_running:
        markup.row(
            types.InlineKeyboardButton("🔴 Stop Bot", callback_data=f"stop_{user_id}_{file_name}"),
            types.InlineKeyboardButton("🔄 Restart", callback_data=f"restart_{user_id}_{file_name}")
        )
    else:
        markup.row(
            types.InlineKeyboardButton("🟢 Start Bot", callback_data=f"start_{user_id}_{file_name}")
        )
    markup.row(
        types.InlineKeyboardButton("📜 View Logs", callback_data=f"logs_{user_id}_{file_name}"),
        types.InlineKeyboardButton("🗑️ Delete File", callback_data=f"delete_{user_id}_{file_name}")
    )
    
    # Custom File Access Controls (for Admins inspecting other users)
    if viewer_id and is_user_admin(viewer_id):
        markup.row(
            types.InlineKeyboardButton("📄 View Code", callback_data=f"adm_viewcode_{user_id}_{file_name}"),
            types.InlineKeyboardButton("✏️ Edit Code", callback_data=f"adm_editcode_{user_id}_{file_name}")
        )
        
    markup.row(
        types.InlineKeyboardButton("🔵 Back to Bot List", callback_data=f"usermg_files_{user_id}" if viewer_id and is_user_admin(viewer_id) and viewer_id != user_id else "back_to_my_bot")
    )
    return markup

# --- Balance & Packages Features ---
def show_balance_packages_menu(message_or_call, user_id):
    is_call = isinstance(message_or_call, types.CallbackQuery)
    chat_id = message_or_call.message.chat.id if is_call else message_or_call.chat.id
    message_id = message_or_call.message.message_id if is_call else None
    
    balance = get_balance(user_id)
    sub_status = "❌ <b>Non-Subscriber</b>"
    if user_id in user_subscriptions:
        expiry = user_subscriptions[user_id].get('expiry')
        if expiry and expiry > datetime.now():
            sub_status = "🟢 <b>Active Subscriber</b>"
    if is_user_admin(user_id) or user_id == OWNER_ID:
        sub_status = "🟢 <b>Active Subscriber (🛡️ Owner/Admin)</b>"

    text = (f"💰 <b>Your Balance & Subscription details</b>\n\n"
            f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
            f"💵 <b>Current Balance:</b> <code>{balance:.2f} Tk</code>\n"
            f"⏳ <b>Subscription Expiry:</b> {sub_status}\n\n"
            f"An active subscription is required to deploy and run bot scripts. Use the buttons below to purchase a plan.")
                    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton("🛍️ Buy Packages", callback_data="buy_packages_list"),
        types.InlineKeyboardButton("📊 Statistics", callback_data="stats")
    )
    
    if is_call:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='HTML')
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

def recharge_balance_command(message):
    user_id = message.from_user.id
    if bot_locked and not is_user_admin(user_id):
        bot.reply_to(message, "⚠️ Bot locked by admin.")
        return
        
    recharge_status = get_setting("recharge_status", "ON")
    if recharge_status == "OFF" and not is_user_admin(user_id):
        bot.reply_to(message, "🔴 Recharge system is currently disabled by Admin.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton("🟥 Bkash", callback_data="paymethod_bkash"),
        types.InlineKeyboardButton("🟧 Nagad", callback_data="paymethod_nagad")
    )
    markup.row(
        types.InlineKeyboardButton("🚀 Rocket", callback_data="paymethod_rocket"),
        types.InlineKeyboardButton("🔶 Binance", callback_data="paymethod_binance")
    )
    
    bot.send_message(message.chat.id, 
                     "💳 *Select Payment Method*\n\nPlease select your preferred payment channel to continue with the recharge:", 
                     reply_markup=markup, parse_mode='Markdown')

def recharge_balance_callback(call):
    user_id = call.from_user.id
    bot.answer_callback_query(call.id)
    
    recharge_status = get_setting("recharge_status", "ON")
    if recharge_status == "OFF" and not is_user_admin(user_id):
        bot.send_message(call.message.chat.id, "🔴 Recharge system is currently disabled by Admin.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton("🟥 Bkash", callback_data="paymethod_bkash"),
        types.InlineKeyboardButton("🟧 Nagad", callback_data="paymethod_nagad")
    )
    markup.row(
        types.InlineKeyboardButton("🚀 Rocket", callback_data="paymethod_rocket"),
        types.InlineKeyboardButton("🔶 Binance", callback_data="paymethod_binance")
    )
    
    bot.edit_message_text("💳 *Select Payment Method*\n\nPlease select your preferred payment channel to continue with the recharge:", 
                           call.message.chat.id, call.message.message_id, 
                           reply_markup=markup, parse_mode='Markdown')

def handle_paymethod_selection(call):
    user_id = call.from_user.id
    method = call.data.replace('paymethod_', '').capitalize()
    bot.answer_callback_query(call.id)
    
    temp_recharges[user_id] = {'method': method}
    
    pay_details = ""
    if method == "Bkash":
        pay_details = "📞 *Bkash Personal Number:* `01722259318`\n💸 Please Send Money to this Bkash number."
    elif method == "Nagad":
        pay_details = "📞 *Nagad Personal Number:* `01722259318`\n💸 Please Send Money to this Nagad number."
    elif method == "Binance":
        pay_details = "🔶 *Binance Pay ID:* `1229559831`\n💸 Please execute payment to this Binance Pay ID."
    elif method == "Rocket":
        pay_details = "🚀 *Rocket Personal Number:* `01722259318`\n💸 Please Send Money to this Rocket number."
    
    msg_text = (f"💳 *Recharge via {method}*\n\n"
                f"{pay_details}\n\n"
                f"After sending, please enter the amount you want to recharge as a number (e.g. 100):\n"
                f"Type /cancel to abort.")
    
    msg = bot.send_message(call.message.chat.id, msg_text, parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_recharge_amount)

def process_recharge_amount(message):
    if check_menu_intercept(message):
        return
    user_id = message.from_user.id
    if message.text and message.text.lower() == '/cancel':
        bot.reply_to(message, "❌ Recharge cancelled.")
        if user_id in temp_recharges:
            del temp_recharges[user_id]
        return
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            raise ValueError()
        if user_id not in temp_recharges:
            temp_recharges[user_id] = {'method': 'Bkash'}
        temp_recharges[user_id]['amount'] = amount
        
        method = temp_recharges[user_id].get('method', 'Payment')
        msg = bot.reply_to(message, f"📞 *Sender Acc / Number ({method})*\n\nPlease enter the {method} number or account ID from which you sent the money:\nType /cancel to abort.", parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_recharge_recipient)
    except Exception:
        msg = bot.reply_to(message, "⚠️ Please enter a valid numerical amount (e.g. 100):")
        bot.register_next_step_handler(msg, process_recharge_amount)

def process_recharge_recipient(message):
    if check_menu_intercept(message):
        return
    user_id = message.from_user.id
    if message.text and message.text.lower() == '/cancel':
        bot.reply_to(message, "❌ Recharge cancelled.")
        if user_id in temp_recharges:
            del temp_recharges[user_id]
        return
    
    recipient = message.text.strip()
    if not recipient:
        msg = bot.reply_to(message, "⚠️ Please enter a valid sender ID/number:")
        bot.register_next_step_handler(msg, process_recharge_recipient)
        return
        
    if user_id not in temp_recharges:
        temp_recharges[user_id] = {'method': 'Bkash', 'amount': 0.0}
    temp_recharges[user_id]['recipient'] = recipient
    msg = bot.reply_to(message, "⏰ *Transaction ID / Time*\n\nPlease enter the Transaction ID (TxID) or sent time:\nType /cancel to abort.", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_recharge_time)

def process_recharge_time(message):
    if check_menu_intercept(message):
        return
    user_id = message.from_user.id
    if message.text and message.text.lower() == '/cancel':
        bot.reply_to(message, "❌ Recharge cancelled.")
        if user_id in temp_recharges:
            del temp_recharges[user_id]
        return
        
    send_time = message.text.strip()
    if not send_time:
        msg = bot.reply_to(message, "⚠️ Please enter a valid TxID/payment time:")
        bot.register_next_step_handler(msg, process_recharge_time)
        return
        
    if user_id not in temp_recharges:
        temp_recharges[user_id] = {'method': 'Bkash', 'amount': 0.0, 'recipient': 'Unknown'}
    temp_recharges[user_id]['send_time'] = send_time
    msg = bot.reply_to(message, "📸 *Payment Screenshot*\n\nPlease send the payment screenshot as a Photo:\nType /cancel to abort.", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_recharge_screenshot)

def process_recharge_screenshot(message):
    if check_menu_intercept(message):
        return
    user_id = message.from_user.id
    if message.text and message.text.lower() == '/cancel':
        bot.reply_to(message, "❌ Recharge cancelled.")
        if user_id in temp_recharges:
            del temp_recharges[user_id]
        return
    
    if not message.photo:
        msg = bot.reply_to(message, "⚠️ Please send the payment screenshot as a photo:")
        bot.register_next_step_handler(msg, process_recharge_screenshot)
        return
        
    photo_file_id = message.photo[-1].file_id
    data = temp_recharges.get(user_id, {})
    amount = data.get('amount', 0.0)
    recipient = data.get('recipient', 'Unknown')
    send_time = data.get('send_time', 'Unknown')
    method = data.get('method', 'Bkash')
    
    deposit_id = str(int(time.time() * 1000))
    save_deposit(deposit_id, user_id, amount, "Pending", photo_file_id, recipient, send_time, method)
        
    if user_id in temp_recharges:
        del temp_recharges[user_id]
        
    bot.reply_to(message, f"✅ Your recharge request of `{amount:.2f} Tk` via *{method}* has been submitted. Please wait for admin verification.", parse_mode='Markdown')
    
    try:
        admin_markup = types.InlineKeyboardMarkup(row_width=2)
        admin_markup.add(
            types.InlineKeyboardButton("✅ Approve", callback_data=f"dep_approve_{deposit_id}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"dep_reject_{deposit_id}")
        )
        caption = (f"📥 *New Deposit Request!*\n\n"
                   f"🆔 User ID: `{user_id}`\n"
                   f"👤 Username: @{message.from_user.username or 'N/A'}\n"
                   f"💳 Method: *{method}*\n"
                   f"💵 Amount: `{amount:.2f} Tk`\n"
                   f"📞 Sender Acc/Num: `{recipient}`\n"
                   f"⏰ TxID / Time: `{send_time}`\n"
                   f"🔢 Deposit ID: `{deposit_id}`")
        bot.send_photo(OWNER_ID, photo_file_id, caption=caption, reply_markup=admin_markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error notifying admin for deposit: {e}")

def handle_deposit_callback(call):
    user_id = call.from_user.id
    if not is_user_admin(user_id):
        bot.answer_callback_query(call.id, "⚠️ Admins only.", show_alert=True)
        return
        
    parts = call.data.split('_')
    action = parts[1]
    deposit_id = parts[2]
    
    dep = get_deposit(deposit_id)
    if not dep:
        bot.answer_callback_query(call.id, "❌ Deposit request not found!", show_alert=True)
        return
        
    target_user_id = int(dep["user_id"])
    amount = float(dep["amount"])
    status = dep["status"]
    
    if status != "Pending":
        bot.answer_callback_query(call.id, f"⚠️ This request was already {status}!", show_alert=True)
        return
        
    if action == "approve":
        update_deposit_status(deposit_id, "Approved")
        
        current_balance = get_balance(target_user_id)
        new_balance = current_balance + amount
        set_balance(target_user_id, new_balance)
        
        bot.answer_callback_query(call.id, "✅ Deposit approved.")
        try:
            bot.send_message(target_user_id, f"🎉 *Recharge Approved!*\n\n💵 Your recharge request of `{amount:.2f} Tk` has been approved by the Admin.\n💰 Current Balance: `{new_balance:.2f} Tk`", parse_mode='Markdown')
        except Exception:
            pass
            
        bot.edit_message_caption(call.message.caption + "\n\n🟢 *Status: Approved ✅*", call.message.chat.id, call.message.message_id, reply_markup=None, parse_mode='Markdown')
        
    elif action == "reject":
        update_deposit_status(deposit_id, "Rejected")
        
        bot.answer_callback_query(call.id, "❌ Deposit rejected.")
        try:
            bot.send_message(target_user_id, f"❌ *Recharge Rejected!*\n\nYour recharge request of `{amount:.2f} Tk` was rejected. Please verify your details and try again.", parse_mode='Markdown')
        except Exception:
            pass
            
        bot.edit_message_caption(call.message.caption + "\n\n🔴 *Status: Rejected ❌*", call.message.chat.id, call.message.message_id, reply_markup=None, parse_mode='Markdown')

def buy_packages_list_callback(call):
    user_id = call.from_user.id
    bot.answer_callback_query(call.id)
    
    packs = get_all_packages()
        
    text = "🛍 *Our Subscription Packages:*\n\n"
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    buttons = []
    for pack_id, pack_info in sorted(packs.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
        name = pack_info.get("name")
        days = pack_info.get("days")
        price = float(pack_info.get("price", 0.0))
        limit_text = f"Limit: {pack_info.get('purchase_limit', 'Unlimited')}" if pack_info.get('purchase_limit', 0) > 0 else "Limit: Unlimited"
        
        price_text = "<b>FREE</b>" if price == 0.0 else f"<code>{price:.2f} Tk</code>"
        
        text += f"Plan ID {pack_id}: *{name}*\n⏳ Validity: `{days} Days` | 💵 Price: {price_text} | 🎯 {limit_text}\n\n"
        buttons.append(types.InlineKeyboardButton(f"🛒 {name} ({'FREE' if price == 0.0 else f'{price:.0f} Tk'})", callback_data=f"buy_pkg_{pack_id}"))
        
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.row(buttons[i], buttons[i+1])
        else:
            markup.row(buttons[i])
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')

def handle_buy_pkg_callback(call):
    user_id = call.from_user.id
    pack_id = call.data.replace('buy_pkg_', '')
    
    sales_status = get_setting("sales_status", "ON")
    if sales_status == "OFF" and not is_user_admin(user_id):
        bot.answer_callback_query(call.id, "🔴 Sales are currently turned OFF by the Admin. Please try again later.", show_alert=True)
        return

    packs = get_all_packages()
    pack = packs.get(pack_id)
    if not pack:
        bot.answer_callback_query(call.id, "❌ Package not found!", show_alert=True)
        return
        
    name = pack.get("name")
    days = int(pack.get("days", 0))
    price = float(pack.get("price", 0.0))
    purchase_limit = int(pack.get("purchase_limit", 0))
    
    if price == 0.0:
        current_expiry = user_subscriptions.get(user_id, {}).get('expiry')
        if current_expiry and current_expiry > datetime.now():
            bot.answer_callback_query(call.id, "❌ Your active package is still valid! You can take the free package again once the validity expires.", show_alert=True)
            return

    if purchase_limit > 0:
        current_purchases = get_purchase_count(user_id, pack_id)
        if current_purchases >= purchase_limit:
            bot.answer_callback_query(call.id, f"❌ Purchase Limit Reached! You can buy/claim this package maximum {purchase_limit} times.", show_alert=True)
            return

    balance = get_balance(user_id)
    
    if price > 0.0:
        if balance < price:
            bot.answer_callback_query(call.id, f"❌ Insufficient balance! Required: {price:.2f} Tk, you have: {balance:.2f} Tk", show_alert=True)
            return
        new_balance = balance - price
        set_balance(user_id, new_balance)

    if purchase_limit > 0:
        increment_purchase_count(user_id, pack_id)

    current_expiry = user_subscriptions.get(user_id, {}).get('expiry')
    new_expiry = calculate_fair_expiry(days, current_expiry)
    save_subscription(user_id, new_expiry)
    
    bot.answer_callback_query(call.id, f"🎉 You have successfully claimed/purchased {name}!", show_alert=True)
    try:
        bot.send_message(OWNER_ID, f"👤 User `{user_id}` purchased `{name}` successfully (Price: {price:.2f} Tk).")
    except Exception:
        pass
        
    show_balance_packages_menu(call, user_id)

# --- Products Catalog Features ---
def show_products_list(message_or_call, user_id):
    is_call = isinstance(message_or_call, types.CallbackQuery)
    chat_id = message_or_call.message.chat.id if is_call else message_or_call.chat.id
    message_id = message_or_call.message.message_id if is_call else None
    
    packs = get_all_packages()
    text = "🛍️ *Please select your subscription plan:*"
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    buttons = []
    for pack_id, pack_info in sorted(packs.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
        name = pack_info.get("name")
        price = float(pack_info.get("price", 0.0))
        price_text = "FREE" if price == 0.0 else f"{price:.0f} Tk"
        buttons.append(types.InlineKeyboardButton(f"🛒 {name} ({price_text})", callback_data=f"buy_pkg_{pack_id}"))
        
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.row(buttons[i], buttons[i+1])
        else:
            markup.row(buttons[i])
    
    if is_call:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='Markdown')
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')

# --- Admin Custom Limits Management ---
def edit_bot_limits_callback(call):
    bot.answer_callback_query(call.id)
    non_sub_lim = get_setting("non_sub_limit", "0")
    sub_lim = get_setting("sub_limit", "3")
    
    text = (f"⚙️ *Bot Limits Customization:*\n\n"
            f"1️⃣ Non-Subscriber Running Limit: `{non_sub_lim}`\n"
            f"2️⃣ Subscriber Running Limit: `{sub_lim}`\n\n"
            f"Select limit to change:")
            
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton("Non-Subscriber Limit", callback_data="modlimit_nonsub"),
        types.InlineKeyboardButton("Subscriber Limit", callback_data="modlimit_sub")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')

def handle_modlimit_callback(call):
    lim_type = call.data.replace('modlimit_', '')
    bot.answer_callback_query(call.id)
    
    msg_text = ""
    if lim_type == "nonsub":
        msg_text = "❌ Enter max running bots for *Non-Subscriber* (e.g. 0):"
    else:
        msg_text = "⭐ Enter max running bots for *Subscriber* (e.g. 3):"
        
    msg = bot.send_message(call.message.chat.id, msg_text, parse_mode='Markdown')
    bot.register_next_step_handler(msg, lambda m: process_modlimit(m, lim_type))

def process_modlimit(message, lim_type):
    user_id = message.from_user.id
    if not is_user_admin(user_id):
        bot.reply_to(message, "⚠️ Admins only.")
        return
    if message.text.lower() == '/cancel':
        bot.reply_to(message, "Limit change cancelled.")
        return
    try:
        new_limit = int(message.text.strip())
        if new_limit < 0:
            raise ValueError()
            
        setting_key = "non_sub_limit" if lim_type == "nonsub" else "sub_limit"
        set_setting(setting_key, new_limit)
        bot.reply_to(message, f"✅ Success! {lim_type.capitalize()} limit set to `{new_limit}`.")
    except Exception:
        bot.reply_to(message, "⚠️ Please enter a valid number (e.g., 3):")

# --- Bot Deployment Flow with Limit & Name Request ---
def _logic_check_files(message, sender_id=None):
    user_id = sender_id if sender_id else message.from_user.id
    if bot_locked and not is_user_admin(user_id):
        bot.reply_to(message, "⚠️ Bot locked by admin.")
        return

    # Admins and Owner completely bypass subscription checks and bot deployment limits!
    if not is_user_admin(user_id) and user_id != OWNER_ID:
        if not has_active_subscription(user_id):
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("🛒 Buy Subscription", callback_data="buy_packages_list"),
                types.InlineKeyboardButton("💵 Recharge", callback_data="recharge_balance")
            )
            bot.reply_to(message, "⚠️ *Subscription Required!*\n\nYou do not have an active subscription. Please purchase a subscription package to access the Deploy Bot panel.", reply_markup=markup, parse_mode='Markdown')
            return

        active_limit = get_active_bot_limit(user_id)
        active_count = get_active_bot_count(user_id)
        if active_count >= active_limit:
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🤖 View My Bot Hub", callback_data="back_to_my_bot")
            )
            bot.reply_to(message, f"⚠️ *Limit Reached!* You can only deploy and run *{active_limit} bots* at a time.\n\nPlease go to your Bot Hub to manage your current bots:", reply_markup=markup, parse_mode='Markdown')
            return

    msg = bot.reply_to(message, "🏷️ *Please enter a name for your Bot Project:*\n(e.g., SmsBot - numbers, letters & underscores only)", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_bot_name_input)

def process_bot_name_input(message):
    if check_menu_intercept(message):
        return
    user_id = message.from_user.id
    bot_name = message.text.strip()
    if not bot_name:
        bot.reply_to(message, "❌ Name cannot be empty. Deployment cancelled.")
        return
        
    bot_name = re.sub(r'[^a-zA-Z0-9_]', '', bot_name)
    if not bot_name:
        bot.reply_to(message, "❌ Invalid name! Use only alphanumeric characters & underscores.")
        return
        
    temp_deploy_name[user_id] = bot_name
    msg = bot.reply_to(message, f"🎯 Name set to: `{bot_name}`\n\n📤 Now send your script file (`Only zip` format into requirements.txt) as a Document:")

# --- File Handling with Malware Detection REMOVED ---
def handle_zip_file(downloaded_file_content, file_name_zip, message):
    user_id = message.from_user.id
    user_folder = get_user_folder(user_id)
    temp_dir = None
    
    bot_base_name = os.path.splitext(file_name_zip)[0]
    
    try:
        temp_dir = tempfile.mkdtemp(prefix=f"user_{user_id}_zip_")
        zip_path = os.path.join(temp_dir, file_name_zip)
        with open(zip_path, 'wb') as new_file:
            new_file.write(downloaded_file_content)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        target_dir = temp_dir
        root_files = os.listdir(target_dir)
        
        if not any(f.endswith(('.py', '.js')) for f in root_files):
            for root, dirs, files in os.walk(temp_dir):
                dirs[:] = [d for d in dirs if not d.startswith('.') and not d.startswith('__')]
                if any(f.endswith(('.py', '.js')) for f in files):
                    target_dir = root
                    break
        
        if target_dir != temp_dir:
            for item in os.listdir(target_dir):
                s = os.path.join(target_dir, item)
                d = os.path.join(temp_dir, item)
                if os.path.exists(d):
                    if os.path.isdir(d): shutil.rmtree(d)
                    else: os.remove(d)
                shutil.move(s, d)
            extracted_items = os.listdir(temp_dir)
        else:
            extracted_items = root_files

        py_files = [f for f in extracted_items if f.endswith('.py')]
        js_files = [f for f in extracted_items if f.endswith('.js')]
        req_file = 'requirements.txt' if 'requirements.txt' in extracted_items else None
        pkg_json = 'package.json' if 'package.json' in extracted_items else None

        if req_file:
            req_path = os.path.join(temp_dir, req_file)
            bot.reply_to(message, f"🔄 Installing `{req_file}`...")
            try:
                command = [sys.executable, '-m', 'pip', 'install', '-r', req_path]
                subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8', errors='ignore')
                bot.reply_to(message, f"✅ Python deps from `{req_file}` installed.")
            except Exception as e:
                 bot.reply_to(message, f"❌ Failed to install Python deps: {e}"); return

        if pkg_json:
            bot.reply_to(message, f"🔄 Installing Node deps from `{pkg_json}`...")
            try:
                command = ['npm', 'install']
                subprocess.run(command, capture_output=True, text=True, check=True, cwd=temp_dir, encoding='utf-8', errors='ignore')
                bot.reply_to(message, f"✅ Node deps from `{pkg_json}` installed.")
            except Exception as e:
                 bot.reply_to(message, f"❌ Failed to install Node deps: {e}"); return

        main_script_name = None; file_type = None
        preferred_py = ['main.py', 'bot.py', 'app.py']
        preferred_js = ['index.js', 'main.js', 'bot.js', 'app.js']
        for p in preferred_py:
            if p in py_files: main_script_name = p; file_type = 'py'; break
        if not main_script_name:
             for p in preferred_js:
                 if p in js_files: main_script_name = p; file_type = 'js'; break
        if not main_script_name:
            if py_files: main_script_name = py_files[0]; file_type = 'py'
            elif js_files: main_script_name = js_files[0]; file_type = 'js'
        if not main_script_name:
            bot.reply_to(message, "❌ No `.py` or `.js` script found in archive!"); return

        new_main_name = f"{bot_base_name}.{file_type}"
        src_main_path = os.path.join(temp_dir, main_script_name)
        dest_main_path = os.path.join(temp_dir, new_main_name)
        if os.path.exists(src_main_path) and src_main_path != dest_main_path:
            shutil.move(src_main_path, dest_main_path)
        main_script_name = new_main_name

        moved_count = 0
        for item_name in os.listdir(temp_dir):
            if item_name == file_name_zip: continue
            src_path = os.path.join(temp_dir, item_name)
            dest_path = os.path.join(user_folder, item_name)
            if os.path.isdir(dest_path): shutil.rmtree(dest_path)
            elif os.path.exists(dest_path): os.remove(dest_path)
            shutil.move(src_path, dest_path); moved_count +=1

        save_user_file(user_id, main_script_name, file_type)
        main_script_path = os.path.join(user_folder, main_script_name)
        bot.reply_to(message, f"💾 Extraction complete. Launching main script: `{main_script_name}`...", parse_mode='Markdown')

        # Recurse & Save entire extracted folder to Supabase storage database
        save_user_folder_to_db(user_id)

        if file_type == 'py':
             threading.Thread(target=run_script, args=(main_script_path, user_id, user_folder, main_script_name, message)).start()
        elif file_type == 'js':
             threading.Thread(target=run_js_script, args=(main_script_path, user_id, user_folder, main_script_name, message)).start()

    except Exception as e:
        logger.error(f"❌ Error processing zip: {e}", exc_info=True)
        bot.reply_to(message, f"❌ Error processing zip: {str(e)}")
    finally:
        if temp_dir and os.path.exists(temp_dir):
            try: shutil.rmtree(temp_dir)
            except Exception: pass

def handle_js_file(file_path, script_owner_id, user_folder, file_name, message):
    try:
        save_user_file(script_owner_id, file_name, 'js')
        save_file_to_db(script_owner_id, file_path)
        threading.Thread(target=run_js_script, args=(file_path, script_owner_id, user_folder, file_name, message)).start()
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

def handle_py_file(file_path, script_owner_id, user_folder, file_name, message):
    try:
        save_user_file(script_owner_id, file_name, 'py')
        save_file_to_db(script_owner_id, file_path)
        threading.Thread(target=run_script, args=(file_path, script_owner_id, user_folder, file_name, message)).start()
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# --- Threaded Document Receiver Background Helper ---
def process_document_background(message, file_info, file_ext, user_folder, file_name):
    user_id = message.from_user.id
    try:
        downloaded_file = bot.download_file(file_info.file_path)
        
        if file_ext == '.zip':
            handle_zip_file(downloaded_file, file_name, message)
            return
            
        file_path = os.path.join(user_folder, file_name)
        with open(file_path, 'wb') as f:
            f.write(downloaded_file)
            
        bot.reply_to(message, f"💾 File saved as `{file_name}`. Launching process...", parse_mode='Markdown')
        
        if file_ext == '.py':
            handle_py_file(file_path, user_id, user_folder, file_name, message)
        elif file_ext == '.js':
            handle_js_file(file_path, user_id, user_folder, file_name, message)
            
    except Exception as e:
        logger.error(f"Error in background doc processing: {e}")
        bot.reply_to(message, f"❌ Error processing file upload: {e}")

@bot.message_handler(content_types=['document'])
def handle_incoming_document(message):
    user_id = message.from_user.id
    if bot_locked and not is_user_admin(user_id):
        bot.reply_to(message, "⚠️ Bot is locked.")
        return
        
    file_info = bot.get_file(message.document.file_id)
    original_name = message.document.file_name
    file_ext = os.path.splitext(original_name)[1].lower()
    
    if file_ext not in ['.py', '.js', '.zip']:
        bot.reply_to(message, "❌ Format not supported! Send only `.py`, `.js` or `.zip` files.")
        return

    # Skip active bot limits check for Admins and Owner!
    if not is_user_admin(user_id) and user_id != OWNER_ID:
        active_limit = get_active_bot_limit(user_id)
        if get_active_bot_count(user_id) >= active_limit:
            bot.reply_to(message, f"⚠️ You already have {active_limit} active bots running. Stop or delete one first using the '🤖 My Bot' menu.")
            return
        
    user_folder = get_user_folder(user_id)
    
    if user_id in temp_deploy_name:
        bot_name = temp_deploy_name[user_id]
        file_name = f"{bot_name}{file_ext}"
        del temp_deploy_name[user_id]
    else:
        bot.reply_to(message, "⚠️ Please click on the *🚀 Deploy Bot* button first to set your bot's name before sending files.", parse_mode='Markdown')
        return
        
    threading.Thread(target=process_document_background, args=(message, file_info, file_ext, user_folder, file_name)).start()

# --- Send Command and Logs Functions ---
def _logic_send_command(message):
    user_id = message.from_user.id
    if bot_locked and not is_user_admin(user_id):
        bot.reply_to(message, "⚠️ Bot locked by admin.")
        return
    bot.reply_to(message, "📤 *Send Command Options:*", reply_markup=create_send_command_menu(), parse_mode='Markdown')

def send_to_process_init(message):
    user_id = message.from_user.id
    user_running_scripts = []
    for script_key, script_info in bot_scripts.items():
        script_owner_id = script_info['script_owner_id']
        if (user_id == script_owner_id or is_user_admin(user_id)) and is_bot_running(script_owner_id, script_info['file_name']):
            user_running_scripts.append((script_key, script_info))
    
    if not user_running_scripts:
        bot.reply_to(message, "❌ No running scripts found.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for script_key, script_info in user_running_scripts:
        btn_text = f"{script_info['file_name']} (User: {script_info['script_owner_id']})"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f'sendcmd_select_{script_key}'))
    
    bot.reply_to(message, "📝 Select a running script to send command to:", reply_markup=markup)

def process_send_command(message, script_key):
    if script_key not in bot_scripts:
        bot.reply_to(message, "❌ Script no longer running.")
        return
    
    script_info = bot_scripts[script_key]
    command_text = message.text
    
    try:
        process = script_info['process']
        if process and process.poll() is None:
            process.stdin.write(command_text + '\n')
            process.stdin.flush()
            bot.reply_to(message, f"✅ Command sent to `{script_info['file_name']}`:\n`{command_text}`", parse_mode='Markdown')
            time.sleep(1)
        else:
            bot.reply_to(message, f"❌ Script `{script_info['file_name']}` is not running.")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

def view_all_logs(message):
    user_id = message.from_user.id
    user_logs = []
    user_folder = get_user_folder(user_id)
    if os.path.exists(user_folder):
        for file in os.listdir(user_folder):
            if file.endswith('.log'):
                log_path = os.path.join(user_folder, file)
                file_size = os.path.getsize(log_path)
                user_logs.append((file, file_size, log_path))
    
    if not user_logs:
        bot.reply_to(message, "📜 No log files found.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for log_file, size, log_path in sorted(user_logs):
        size_kb = size / 1024
        btn_text = f"{log_file} ({size_kb:.1f} KB)"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f'viewlog_{user_id}_{log_file}'))
    
    bot.reply_to(message, "📜 Available Log Files:", reply_markup=markup)

def send_log_file(message, log_path, log_filename):
    try:
        file_size = os.path.getsize(log_path)
        if file_size > 50 * 1024 * 1024:
            bot.reply_to(message, "❌ Log file too large.")
            return
        
        with open(log_path, 'rb') as log_file:
            bot.send_document(message.chat.id, log_file, caption=f"📜 {log_filename}")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# --- Logic Functions ---
def _logic_send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_username = message.from_user.username or "N/A"

    if bot_locked and not is_user_admin(user_id):
        bot.send_message(chat_id, "⚠️ Bot locked by admin. Try later.")
        return

    add_active_user(user_id, f"@{user_username}")
    
    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
    expiry_info = ""
    balance = get_balance(user_id)
    
    if user_id == OWNER_ID: 
        user_status = "👑 Owner"
    elif is_user_admin(user_id): 
        user_status = "🛡️ Admin"
    elif user_id in user_subscriptions:
        expiry_date = user_subscriptions[user_id].get('expiry')
        if expiry_date and expiry_date > datetime.now():
            user_status = "Subscriber"
            days_left = (expiry_date - datetime.now()).days
            expiry_info = f"\n⏳ Expiry Time: {days_left} days remaining"
        else: 
            user_status = "Non-Subscriber"
            remove_subscription_db(user_id)
    else: 
        user_status = "Non-Subscriber"

    welcome_msg_text = (f"💠 <b>WELCOME TO MINO BOT HOSTING</b> 💠\n"
                        f"────────────────────────\n"
                        f"👤 <b>USER ID:</b> <code>{user_id}</code>\n"
                        f"✳️ <b>USERNAME:</b> <code>@{user_username}</code>\n"
                        f"💵 <b>YOUR BALANCE:</b> <code>{balance:.2f} Tk</code>\n"
                        f"🔰 <b>STATUS:</b> <code>{user_status}</code>{expiry_info}\n"
                        f"📂 <b>FILES UPLOADED:</b> <code>{current_files} / {limit_str}</code>\n"
                        f"────────────────────────\n"
                        f"🤖 You can host and run Python (<code>.py</code>) and JavaScript (<code>.js</code>) scripts smoothly in real-time.\n\n"
                        f"👇 Use the menu buttons below to access your desired services.")
    
    main_reply_markup = create_reply_keyboard_main_menu(user_id)
    bot.send_message(chat_id, welcome_msg_text, reply_markup=main_reply_markup, parse_mode='HTML')

def _logic_balance_packages(message):
    user_id = message.from_user.id
    if bot_locked and not is_user_admin(user_id):
        bot.reply_to(message, "⚠️ Bot locked by admin.")
        return
    show_balance_packages_menu(message, user_id)

def _logic_upload_file(message, sender_id=None):
    _logic_check_files(message, sender_id)

# --- "My Bot" Menu Feature Implementation ---
def _logic_my_bot(message):
    user_id = message.from_user.id
    show_my_bot_status(message.chat.id, user_id)
    
def show_my_bot_status(chat_id, user_id, message_id=None):
    user_files_list = user_files.get(user_id, [])
    sub_status = "❌ Non-Subscriber"
    if user_id in user_subscriptions:
        expiry = user_subscriptions[user_id].get('expiry')
        if expiry and expiry > datetime.now():
            days_left = (expiry - datetime.now()).days
            sub_status = f"🟢 Subscriber ({days_left} Days Remaining)"
    if is_user_admin(user_id) or user_id == OWNER_ID:
        sub_status = "🟢 Active Subscriber (🛡️ Owner/Admin)"

    text = f"🤖 *Your Bot Hub*\n\n⏳ *Subscription status:* {sub_status}\n\n"
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    if user_files_list:
        text += "📂 *Your Deployed Bots:*\nSelect a bot from the list below to view its statistics and manage it:"
        for file_name, file_type in sorted(user_files_list):
            is_running = is_bot_running(user_id, file_name)
            status_icon = "🟢" if is_running else "🔴"
            markup.add(types.InlineKeyboardButton(f"{status_icon} {file_name}", callback_data=f"file_{user_id}_{file_name}"))
    else:
        text += "❌ *No bot deployed yet!*\n\nClick below to deploy your first bot."
        markup.add(types.InlineKeyboardButton("🚀 Deploy Bot", callback_data="upload"))
            
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='Markdown')
        except Exception:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')

def calculate_speed_percentage(latency_ms):
    cpu = psutil.cpu_percent()
    base_speed = 100.0 - (cpu * 0.3)
    if latency_ms < 150:
        deduction = latency_ms * 0.02
    elif latency_ms < 500:
        deduction = 3.0 + (latency_ms * 0.03)
    else:
        deduction = 15.0 + (latency_ms * 0.01)
    speed = max(15.0, min(100.0, base_speed - deduction))
    return round(speed, 1)

def _logic_bot_speed(message, sender_id=None):
    user_id = sender_id if sender_id else message.from_user.id
    chat_id = message.chat.id
    start_time_ping = time.time()
    wait_msg = bot.reply_to(message, "🏃 Testing speed...")
    try:
        bot.send_chat_action(chat_id, 'typing')
        latency = (time.time() - start_time_ping) * 1000
        speed_percent = calculate_speed_percentage(latency)
        status = "🔓 Unlocked" if not bot_locked else "🔒 Locked"
        if user_id == OWNER_ID: user_level = "👑 Owner"
        elif is_user_admin(user_id): user_level = "🛡️ Admin"
        elif user_id in user_subscriptions and user_subscriptions[user_id].get('expiry', datetime.min) > datetime.now(): user_level = "⭐ Premium"
        else: user_level = "🆓 Free User"
        
        speed_msg = (f"⚡ *Bot Speed & Status:*\n\n"
                     f"⏱️ API Response: `{latency:.2f} ms`\n"
                     f"📈 *Speed Percentage: {speed_percent}% / 100%*\n"
                     f"🚦 Bot Status: `{status}`\n"
                     f"👤 Your Level: `{user_level}`")
        bot.edit_message_text(speed_msg, chat_id, wait_msg.message_id, parse_mode='Markdown')
    except Exception:
        bot.edit_message_text("❌ Error during speed test.", chat_id, wait_msg.message_id)

def _logic_contact_owner(message):
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton('📞 Contact Owner', url=f'https://t.me/{YOUR_USERNAME.replace("@", "")}')
    )
    bot.reply_to(message, "Click to contact Owner:", reply_markup=markup)

# --- Admin Panel & User Files Access Features ---
def _logic_subscriptions_panel(message):
    if not is_user_admin(message.from_user.id):
        bot.reply_to(message, "⚠️ Admin permissions required.")
        return
    bot.reply_to(message, "💳 Subscription Management", reply_markup=create_subscription_menu())

def get_runtime_string(start_time):
    duration = datetime.now() - start_time
    seconds = int(duration.total_seconds())
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}h {minutes:02d}m {secs:02d}s"

def _logic_statistics(message, sender_id=None):
    user_id = sender_id if sender_id else message.from_user.id
    total_users = len(active_users)
    total_files_records = sum(len(files) for files in user_files.values())

    running_bots_count = 0
    user_running_bots = []

    for script_key_iter, script_info_iter in list(bot_scripts.items()):
        s_owner_id, _ = script_key_iter.split('_', 1)
        if is_bot_running(int(s_owner_id), script_info_iter['file_name']):
            running_bots_count += 1
            if int(s_owner_id) == user_id:
                user_running_bots.append(script_info_iter)

    stats_msg = (f"📊 *Bot Statistics*\n\n"
                 f"💠 Total Users: `{total_users}`\n"
                 f"📂 Total File Records: `{total_files_records}`\n"
                 f"🟢 Total Active Bots: `{running_bots_count}`\n\n")

    stats_msg += f"🤖 *Your Running Bots ({len(user_running_bots)}):*\n"
    if user_running_bots:
        for script in user_running_bots:
            runtime_str = get_runtime_string(script['start_time'])
            stats_msg += f"🔸 `{script['file_name']}` | Runtime: `{runtime_str}`\n"
    else:
        stats_msg += "*(No active bots running)*\n"

    if is_user_admin(user_id):
        status_lock = '🔴 Locked' if bot_locked else '🟢 Unlocked'
        stats_msg += f"\n🛡️ *Admin Status:*\n🚦 Bot Lock Status: `{status_lock}`"

    bot.reply_to(message, stats_msg, parse_mode='Markdown')

def _logic_broadcast_init(message, sender_id=None):
    user_id = sender_id if sender_id else message.from_user.id
    if not is_user_admin(user_id):
        bot.reply_to(message, "⚠️ Admin permissions required.")
        return
    msg = bot.reply_to(message, "📢 Send message to broadcast to all active users.\n/cancel to abort.")
    bot.register_next_step_handler(msg, process_broadcast_message)

def _logic_toggle_lock_bot(message):
    if not is_user_admin(message.from_user.id):
        bot.reply_to(message, "⚠️ Admin permissions required.")
        return
    global bot_locked
    bot_locked = not bot_locked
    status = "locked" if bot_locked else "unlocked"
    bot.reply_to(message, f"🔒 Bot has been {status}.")

def _logic_admin_panel(message):
    if not is_user_admin(message.from_user.id):
        bot.reply_to(message, "⚠️ Admin permissions required.")
        return
    bot.reply_to(message, "👑 Admin Panel\nManage admins & users. Use inline buttons.",
                 reply_markup=create_admin_panel())

def _logic_run_all_scripts(message_or_call):
    if isinstance(message_or_call, telebot.types.Message):
        admin_user_id = message_or_call.from_user.id
        admin_chat_id = message_or_call.chat.id
        reply_func = lambda text, **kwargs: bot.reply_to(message_or_call, text, **kwargs)
        admin_message_obj = message_or_call
    elif isinstance(message_or_call, telebot.types.CallbackQuery):
        admin_user_id = message_or_call.from_user.id
        admin_chat_id = message_or_call.message.chat.id
        bot.answer_callback_query(call_id=message_or_call.id)
        reply_func = lambda text, **kwargs: bot.send_message(admin_chat_id, text, **kwargs)
        admin_message_obj = message_or_call.message
    else:
        return

    if not is_user_admin(admin_user_id):
        reply_func("⚠️ Admin permissions required.")
        return

    reply_func("⏳ Starting process to run all user scripts...")

    started_count = 0; attempted_users = 0; skipped_files = 0
    all_user_files_snapshot = dict(user_files)

    for target_user_id, files_for_user in all_user_files_snapshot.items():
        if not files_for_user: continue
        attempted_users += 1
        user_folder = get_user_folder(target_user_id)

        for file_name, file_type in files_for_user:
            if not is_bot_running(target_user_id, file_name):
                file_path = os.path.join(user_folder, file_name)
                if os.path.exists(file_path):
                    try:
                        if file_type == 'py':
                            threading.Thread(target=run_script, args=(file_path, target_user_id, user_folder, file_name, admin_message_obj)).start()
                            started_count += 1
                        elif file_type == 'js':
                            threading.Thread(target=run_js_script, args=(file_path, target_user_id, user_folder, file_name, admin_message_obj)).start()
                            started_count += 1
                        time.sleep(0.7)
                    except Exception:
                        skipped_files += 1
                else:
                    skipped_files += 1

    summary_msg = (f"✅ All Users' Scripts - Processing Complete:\n\n"
                   f"▶️ Attempted to start: {started_count} scripts.\n"
                   f"👥 Users processed: {attempted_users}.\n")
                   
    reply_func(summary_msg, parse_mode='Markdown')

# --- Monitor Running Bots via Admin Panel ---
def admin_running_bots_callback(call):
    user_id = call.from_user.id
    if not is_user_admin(user_id):
        bot.answer_callback_query(call.id, "⚠️ Admin permissions required.", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    
    running_bots = []
    for script_key, script_info in list(bot_scripts.items()):
        owner_id = script_info.get('script_owner_id')
        file_name = script_info.get('file_name')
        if is_bot_running(owner_id, file_name):
            running_bots.append((owner_id, file_name, script_info.get('start_time')))
            
    if not running_bots:
        bot.send_message(call.message.chat.id, "🟢 *Running Bots*\n\n*(No active bots currently running)*", parse_mode='Markdown')
        return
        
    msg_text = f"🟢 *Currently Running Bots ({len(running_bots)}):*\n\n"
    for owner, file, start_time in running_bots:
        runtime_str = get_runtime_string(start_time) if start_time else "N/A"
        msg_text += (f"👤 *User ID:* `{owner}`\n"
                     f"📂 *File:* `{file}`\n"
                     f"⏱️ *Runtime:* `{runtime_str}`\n\n"
                     f"--------------------\n")
                     
    bot.send_message(call.message.chat.id, msg_text, parse_mode='Markdown')

# --- Manage User Panel ---
def admin_manage_user_init(call):
    user_id = call.from_user.id
    if not is_user_admin(user_id):
        bot.answer_callback_query(call.id, "⚠️ Admin permissions required.", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "👤 <b>User Management Panel</b>\n\nPlease enter the Telegram User ID of the user you want to inspect/manage:", parse_mode='HTML')
    bot.register_next_step_handler(msg, process_admin_manage_user)

def process_admin_manage_user(message):
    if check_menu_intercept(message):
        return
    try:
        target_id = int(message.text.strip())
        show_user_management_panel(message.chat.id, target_id)
    except Exception:
        bot.reply_to(message, "❌ Invalid User ID! Please enter a numerical User ID.")

def show_user_management_panel(chat_id, target_id):
    balance = get_balance(target_id)
    expiry = user_subscriptions.get(target_id, {}).get('expiry')
    
    # Track join date & registration period
    user_info = get_user_info(target_id)
    join_date_str = "N/A"
    duration_str = "N/A"
    username = user_info.get("username", "N/A")
    join_date = user_info.get("join_date")
    if join_date:
        try:
            if isinstance(join_date, str):
                join_date = datetime.fromisoformat(join_date)
            join_date_str = join_date.strftime("%Y-%m-%d %H:%M")
            if join_date.tzinfo is not None:
                join_date = join_date.replace(tzinfo=None)
            diff = datetime.now() - join_date
            if diff.days > 0:
                duration_str = f"{diff.days} Days ago"
            else:
                hours = diff.seconds // 3600
                mins = (diff.seconds % 3600) // 60
                duration_str = f"{hours}h {mins}m ago"
        except Exception as e:
            logger.error(f"Error parsing join date: {e}")
            pass

    sub_status = "❌ <b>Non-Subscriber</b>"
    days_remaining = 0
    if expiry:
        if expiry > datetime.now():
            sub_status = "🟢 <b>Active Subscriber</b>"
            days_remaining = (expiry - datetime.now()).days
        else:
            sub_status = "🔴 <b>Expired</b>"
            
    user_files_list = user_files.get(target_id, [])
    total_files = len(user_files_list)
    active_bots = get_active_bot_count(target_id)
    
    text = (f"👤 <b>User Control Panel</b>\n\n"
            f"🆔 <b>User ID:</b> <code>{target_id}</code>\n"
            f"👤 <b>Username:</b> {username}\n"
            f"📅 <b>Registered:</b> <code>{join_date_str}</code> ({duration_str})\n"
            f"💵 <b>Current Balance:</b> <code>{balance:.2f} Tk</code>\n"
            f"💳 <b>Subscription status:</b> {sub_status}\n"
            f"⏳ <b>Days Remaining:</b> <code>{days_remaining} Days</code>\n"
            f"📂 <b>Total Files Deployed:</b> <code>{total_files}</code>\n"
            f"🟢 <b>Active Running Bots:</b> <code>{active_bots}</code>\n\n"
            f"👇 Use the quick-actions below to manage this user:")
            
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton("🟢 Add Balance", callback_data=f"usermg_addbal_{target_id}"),
        types.InlineKeyboardButton("🔴 Deduct Balance", callback_data=f"usermg_subbal_{target_id}")
    )
    markup.row(
        types.InlineKeyboardButton("✏️ Set Balance", callback_data=f"usermg_setbal_{target_id}"),
        types.InlineKeyboardButton("📅 Edit Sub Days", callback_data=f"usermg_sub_{target_id}")
    )
    markup.row(
        types.InlineKeyboardButton("📂 View & Edit Files", callback_data=f"usermg_files_{target_id}"),
        types.InlineKeyboardButton("❌ Remove Sub", callback_data=f"usermg_rem_{target_id}")
    )
    markup.row(
        types.InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")
    )
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

# --- Admin User Files Access Controllers ---
def usermg_files_callback(call):
    parts = call.data.split('_')
    target_id = int(parts[2])
    bot.answer_callback_query(call.id)
    show_admin_user_files(call.message.chat.id, target_id)
    
def show_admin_user_files(chat_id, target_id):
    user_files_list = user_files.get(target_id, [])
    text = f"📂 *Files List of User ID:* `{target_id}`\n\nClick on any file to view stats, inspect code, edit/overwrite, stop, run, or delete:"
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    if not user_files_list:
        text += "\n*(No files uploaded by this user)*"
    else:
        for file_name, file_type in sorted(user_files_list):
            is_running = is_bot_running(target_id, file_name)
            status_icon = "🟢" if is_running else "🔴"
            markup.add(types.InlineKeyboardButton(f"{status_icon} {file_name}", callback_data=f"file_{target_id}_{file_name}"))
            
    markup.add(types.InlineKeyboardButton("🔙 Back to User Panel", callback_data=f"admin_inspect_user_{target_id}"))
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')

def admin_inspect_user_callback(call):
    target_id = int(call.data.replace('admin_inspect_user_', ''))
    bot.answer_callback_query(call.id)
    show_user_management_panel(call.message.chat.id, target_id)

# --- User Management Balance/Sub Handlers ---
def usermg_addbal_callback(call):
    target_id = int(call.data.replace('usermg_addbal_', ''))
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, f"➕ <b>Add Balance to User</b> <code>{target_id}</code>\n\nEnter the amount of money you want to ADD (e.g. 50):", parse_mode='HTML')
    bot.register_next_step_handler(msg, lambda m: process_usermg_addbal(m, target_id))

def process_usermg_addbal(message, target_id):
    if check_menu_intercept(message):
        return
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            raise ValueError()
        current = get_balance(target_id)
        set_balance(target_id, current + amount)
        bot.reply_to(message, f"🟢 <b>Success!</b> Added <code>{amount:.2f} Tk</code> to User <code>{target_id}</code>.", parse_mode='HTML')
        show_user_management_panel(message.chat.id, target_id)
    except Exception:
        bot.reply_to(message, "❌ Invalid amount! Please enter a positive number.")

def usermg_subbal_callback(call):
    target_id = int(call.data.replace('usermg_subbal_', ''))
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, f"➖ <b>Deduct Balance from User</b> <code>{target_id}</code>\n\nEnter the amount of money you want to DEDUCT (e.g. 20):", parse_mode='HTML')
    bot.register_next_step_handler(msg, lambda m: process_usermg_subbal(m, target_id))

def process_usermg_subbal(message, target_id):
    if check_menu_intercept(message):
        return
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            raise ValueError()
        current = get_balance(target_id)
        set_balance(target_id, max(0.0, current - amount))
        bot.reply_to(message, f"🟢 <b>Success!</b> Deducted <code>{amount:.2f} Tk</code> from User <code>{target_id}</code>.", parse_mode='HTML')
        show_user_management_panel(message.chat.id, target_id)
    except Exception:
        bot.reply_to(message, "❌ Invalid amount! Please enter a positive number.")

def usermg_setbal_callback(call):
    target_id = int(call.data.replace('usermg_setbal_', ''))
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, f"✏️ <b>Set Exact Balance for User</b> <code>{target_id}</code>\n\nEnter the exact balance amount (e.g. 100):", parse_mode='HTML')
    bot.register_next_step_handler(msg, lambda m: process_usermg_setbal(m, target_id))

def process_usermg_setbal(message, target_id):
    if check_menu_intercept(message):
        return
    try:
        amount = float(message.text.strip())
        if amount < 0:
            raise ValueError()
        set_balance(target_id, amount)
        bot.reply_to(message, f"🟢 <b>Success!</b> Exact balance of User <code>{target_id}</code> set to <code>{amount:.2f} Tk</code>.", parse_mode='HTML')
        show_user_management_panel(message.chat.id, target_id)
    except Exception:
        bot.reply_to(message, "❌ Invalid amount! Please enter a valid number.")

def usermg_sub_callback(call):
    target_id = int(call.data.replace('usermg_sub_', ''))
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, f"📅 <b>Edit Subscription Days for User</b> <code>{target_id}</code>\n\nEnter the number of days to set/add (e.g. 30):", parse_mode='HTML')
    bot.register_next_step_handler(msg, lambda m: process_usermg_sub(m, target_id))

def process_usermg_sub(message, target_id):
    if check_menu_intercept(message):
        return
    try:
        days = int(message.text.strip())
        current_expiry = user_subscriptions.get(target_id, {}).get('expiry')
        new_expiry = calculate_fair_expiry(days, current_expiry)
        save_subscription(target_id, new_expiry)
        bot.reply_to(message, f"🟢 <b>Success!</b> Subscription updated. New Expiry: <code>{new_expiry.isoformat()}</code>", parse_mode='HTML')
        show_user_management_panel(message.chat.id, target_id)
    except Exception as e:
        bot.reply_to(message, f"❌ Invalid input! Error: {e}")

def usermg_rem_callback(call):
    target_id = int(call.data.replace('usermg_rem_', ''))
    remove_subscription_db(target_id)
    bot.answer_callback_query(call.id, "❌ Subscription successfully removed!", show_alert=True)
    show_user_management_panel(call.message.chat.id, target_id)

def usermg_bal_callback(call):
    bot.answer_callback_query(call.id)

# --- Package Customization Panel ---
def admin_edit_packages_callback(call):
    bot.answer_callback_query(call.id)
    packs = get_all_packages()
        
    text = "📦 <b>Package Management Panel</b>\n\nSelect a subscription package to edit its details (Name, Price, Validity, or Purchase Limit):"
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    buttons = []
    for pack_id, pack_info in sorted(packs.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
        name = pack_info.get("name")
        price = float(pack_info.get("price", 0.0))
        buttons.append(types.InlineKeyboardButton(f"⚙️ {name} ({price:.0f} Tk)", callback_data=f"admin_pkg_manage_{pack_id}"))
        
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.row(buttons[i], buttons[i+1])
        else:
            markup.row(buttons[i])
            
    markup.row(
        types.InlineKeyboardButton("➕ Add Product", callback_data="admin_pkg_add_init"),
        types.InlineKeyboardButton("🔵 Admin Panel", callback_data="admin_panel")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')

def admin_pkg_manage_callback(call):
    pack_id = call.data.replace('admin_pkg_manage_', '')
    bot.answer_callback_query(call.id)
    show_package_admin_panel(call.message.chat.id, pack_id)

def show_package_admin_panel(chat_id, pack_id):
    packs = get_all_packages()
    pack = packs.get(pack_id)
    if not pack:
        bot.send_message(chat_id, "❌ Package not found!")
        return
        
    name = pack.get("name")
    days = pack.get("days")
    price = float(pack.get("price", 0.0))
    purchase_limit = int(pack.get("purchase_limit", 0))
    limit_text = f"<code>{purchase_limit}</code> times" if purchase_limit > 0 else "<code>Unlimited</code>"
    price_text = "<code>FREE (0 Tk)</code>" if price == 0.0 else f"<code>{price:.2f} Tk</code>"
    
    text = (f"⚙️ <b>Managing Package ID: {pack_id}</b>\n\n"
            f"🏷️ <b>Current Name:</b> <code>{name}</code>\n"
            f"💵 <b>Current Price:</b> {price_text}\n"
            f"⏳ <b>Current Validity:</b> <code>{days} Days</code>\n"
            f"🎯 <b>Purchase Limit:</b> {limit_text}\n\n"
            f"Select which field you want to modify:")
            
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton("🏷️ Edit Name", callback_data=f"admin_pkg_name_{pack_id}"),
        types.InlineKeyboardButton("💵 Edit Price", callback_data=f"admin_pkg_price_{pack_id}")
    )
    markup.row(
        types.InlineKeyboardButton("⏳ Edit Days", callback_data=f"admin_pkg_days_{pack_id}"),
        types.InlineKeyboardButton("🎯 Edit Limit", callback_data=f"admin_pkg_limit_{pack_id}")
    )
    markup.row(
        types.InlineKeyboardButton("🔙 Back to List", callback_data="admin_edit_packages")
    )
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

def admin_pkg_name_callback(call):
    pack_id = call.data.replace('admin_pkg_name_', '')
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, f"✏️ <b>Enter new Name for Package ID {pack_id}:</b>", parse_mode='HTML')
    bot.register_next_step_handler(msg, lambda m: process_admin_pkg_name(m, pack_id))
    
def process_admin_pkg_name(message, pack_id):
    if check_menu_intercept(message):
        return
    new_name = message.text.strip()
    if not new_name:
        bot.reply_to(message, "❌ Name cannot be empty!")
        return
    
    update_package(pack_id, "name", new_name)
    
    bot.reply_to(message, f"🟢 <b>Success!</b> Package name updated to <code>{new_name}</code>.", parse_mode='HTML')
    show_package_admin_panel(message.chat.id, pack_id)

def admin_pkg_price_callback(call):
    pack_id = call.data.replace('admin_pkg_price_', '')
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, f"✏️ <b>Enter new Price (Tk) for Package ID {pack_id} (0 = Free):</b>", parse_mode='HTML')
    bot.register_next_step_handler(msg, lambda m: process_admin_pkg_price(m, pack_id))
    
def process_admin_pkg_price(message, pack_id):
    if check_menu_intercept(message):
        return
    try:
        new_price = float(message.text.strip())
        if new_price < 0:
            raise ValueError()
        
        update_package(pack_id, "price", new_price)
        
        msg_val = "FREE" if new_price == 0.0 else f"{new_price:.2f} Tk"
        bot.reply_to(message, f"🟢 <b>Success!</b> Package price updated to <code>{msg_val}</code>.", parse_mode='HTML')
        show_package_admin_panel(message.chat.id, pack_id)
    except Exception:
        bot.reply_to(message, "❌ Invalid price amount! Enter a positive number.")

def admin_pkg_days_callback(call):
    pack_id = call.data.replace('admin_pkg_days_', '')
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, f"✏️ <b>Enter new Validity (Days) for Package ID {pack_id}:</b>", parse_mode='HTML')
    bot.register_next_step_handler(msg, lambda m: process_admin_pkg_days(m, pack_id))
    
def process_admin_pkg_days(message, pack_id):
    if check_menu_intercept(message):
        return
    try:
        new_days = int(message.text.strip())
        if new_days <= 0:
            raise ValueError()
            
        update_package(pack_id, "days", new_days)
        
        bot.reply_to(message, f"🟢 <b>Success!</b> Package validity updated to <code>{new_days} Days</code>.", parse_mode='HTML')
        show_package_admin_panel(message.chat.id, pack_id)
    except Exception:
        bot.reply_to(message, "❌ Invalid validity days! Enter a positive integer.")

def admin_pkg_limit_callback(call):
    pack_id = call.data.replace('admin_pkg_limit_', '')
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, f"🎯 <b>Enter new Purchase Limit for Package ID {pack_id} (0 = Unlimited):</b>", parse_mode='HTML')
    bot.register_next_step_handler(msg, lambda m: process_admin_pkg_limit(m, pack_id))

def process_admin_pkg_limit(message, pack_id):
    if check_menu_intercept(message):
        return
    try:
        new_limit = int(message.text.strip())
        if new_limit < 0:
            raise ValueError()
            
        update_package(pack_id, "purchase_limit", new_limit)
        
        limit_val = "Unlimited" if new_limit == 0 else f"{new_limit} times"
        bot.reply_to(message, f"🟢 <b>Success!</b> Purchase limit updated to <code>{limit_val}</code>.", parse_mode='HTML')
        show_package_admin_panel(message.chat.id, pack_id)
    except Exception:
        bot.reply_to(message, "❌ Invalid limit! Enter a positive integer (0 for unlimited).")

# --- Dynamically Add Products/Packages ---
def admin_pkg_add_init_callback(call):
    user_id = call.from_user.id
    if not is_user_admin(user_id):
        bot.answer_callback_query(call.id, "⚠️ Admin permissions required.", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📦 <b>Add New Product / Package</b>\n\nPlease enter the Package Name (e.g. '60 Days VPS Plan'):", parse_mode='HTML')
    bot.register_next_step_handler(msg, process_admin_add_pkg_name)

def process_admin_add_pkg_name(message):
    if check_menu_intercept(message):
        return
    name = message.text.strip()
    if not name:
        bot.reply_to(message, "❌ Name cannot be empty! Process cancelled.")
        return
    msg = bot.reply_to(message, f"🏷️ Name set to: <code>{name}</code>\n\nNow, enter the validity period in <b>Days</b> (e.g. 60):", parse_mode='HTML')
    bot.register_next_step_handler(msg, lambda m: process_admin_add_pkg_days(m, name))

def process_admin_add_pkg_days(message, name):
    if check_menu_intercept(message):
        return
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError()
        msg = bot.reply_to(message, f"🏷️ Name: <code>{name}</code>\n⏳ Validity: <code>{days} Days</code>\n\nNow, enter the price in <b>Tk</b> (e.g. 299, 0 = Free):", parse_mode='HTML')
        bot.register_next_step_handler(msg, lambda m: process_admin_add_pkg_price(m, name, days))
    except Exception:
        msg = bot.reply_to(message, "❌ Invalid validity! Please enter a valid positive number of days:")
        bot.register_next_step_handler(msg, lambda m: process_admin_add_pkg_days(m, name))

def process_admin_add_pkg_price(message, name, days):
    if check_menu_intercept(message):
        return
    try:
        price = float(message.text.strip())
        if price < 0:
            raise ValueError()
        
        packs = get_all_packages()
        existing_ids = [int(k) for k in packs.keys() if k.isdigit()]
        next_id = str(max(existing_ids) + 1) if existing_ids else "1"
        
        add_package(next_id, name, days, price, 0)
        
        bot.reply_to(message, f"🟢 <b>Success!</b> New package added successfully:\n\n"
                              f"🆔 <b>ID:</b> <code>{next_id}</code>\n"
                              f"🏷️ <b>Name:</b> <code>{name}</code>\n"
                              f"⏳ <b>Validity:</b> <code>{days} Days</code>\n"
                              f"💵 <b>Price:</b> <code>{price:.2f} Tk</code>\n"
                              f"🎯 <b>Purchase Limit:</b> <code>Unlimited</code>", parse_mode='HTML')
        show_package_admin_panel(message.chat.id, next_id)
    except Exception:
        msg = bot.reply_to(message, "❌ Invalid price! Enter a valid numerical amount:")
        bot.register_next_step_handler(msg, lambda m: process_admin_add_pkg_price(m, name, days))

# --- Global Sales ON/OFF ---
def admin_toggle_sales_callback(call):
    user_id = call.from_user.id
    if not is_user_admin(user_id):
        bot.answer_callback_query(call.id, "⚠️ Admin permissions required.", show_alert=True)
        return
    
    current_status = get_setting("sales_status", "ON")
    new_status = "OFF" if current_status == "ON" else "ON"
    set_setting("sales_status", new_status)
    
    bot.answer_callback_query(call.id, f"✅ Sales turned {new_status}!", show_alert=True)
    admin_panel_callback(call)

# --- Global Recharge ON/OFF ---
def admin_toggle_recharge_callback(call):
    user_id = call.from_user.id
    if not is_user_admin(user_id):
        bot.answer_callback_query(call.id, "⚠️ Admin permissions required.", show_alert=True)
        return
    
    current_status = get_setting("recharge_status", "ON")
    new_status = "OFF" if current_status == "ON" else "ON"
    set_setting("recharge_status", new_status)
    
    bot.answer_callback_query(call.id, f"✅ Recharge system turned {new_status}!", show_alert=True)
    admin_panel_callback(call)

# --- Direct Callback Mapping Wrappers ---
def admin_required_callback(call, func):
    if is_user_admin(call.from_user.id):
        func(call)
    else:
        bot.answer_callback_query(call.id, "⚠️ Admin permissions required.", show_alert=True)

def owner_required_callback(call, func):
    if call.from_user.id == OWNER_ID or call.from_user.id == ADMIN_ID:
        func(call)
    else:
        bot.answer_callback_query(call.id, "⚠️ Owner permissions required.", show_alert=True)

def upload_callback(call):
    bot.answer_callback_query(call.id)
    _logic_upload_file(call.message, sender_id=call.from_user.id)

def check_files_callback(call):
    bot.answer_callback_query(call.id)
    _logic_check_files(call.message, sender_id=call.from_user.id)

def file_control_callback(call):
    bot.answer_callback_query(call.id)
    parts = call.data.split('_')
    script_owner_id = int(parts[1])
    file_name = "_".join(parts[2:])
    is_running = is_bot_running(script_owner_id, file_name)
    status_str = "🟢 Active" if is_running else "🔴 Stopped"
    
    # Get subscription status for display
    sub_status = "❌ Non-Subscriber"
    if script_owner_id in user_subscriptions:
        expiry = user_subscriptions[script_owner_id].get('expiry')
        if expiry and expiry > datetime.now():
            days_left = (expiry - datetime.now()).days
            sub_status = f"🟢 Subscriber ({days_left} Days)"
    if is_user_admin(script_owner_id) or script_owner_id == OWNER_ID:
        sub_status = "🟢 Active Subscriber (🛡️ Owner/Admin)"

    # Get file upload duration details
    user_folder = get_user_folder(script_owner_id)
    file_path = os.path.join(user_folder, file_name)
    upload_time_str = "N/A"
    if os.path.exists(file_path):
        file_info = get_file_info(script_owner_id, file_name)
        if file_info and file_info.get("upload_time"):
            try:
                upload_time = file_info["upload_time"]
                if isinstance(upload_time, str):
                    upload_time = datetime.fromisoformat(upload_time)
                upload_time_str = upload_time.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
        else:
            ctime = os.path.getctime(file_path)
            upload_time_str = datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M")

    runtime_info = ""
    script_key = f"{script_owner_id}_{file_name}"
    if is_running and script_key in bot_scripts:
        start_time = bot_scripts[script_key].get('start_time')
        if start_time:
            duration = datetime.now() - start_time
            hours = int(duration.total_seconds() // 3600)
            minutes = int((duration.total_seconds() % 3600) // 60)
            runtime_info = f"\n⏱️ *Running duration:* `{hours} hours {minutes} mins`"
    
    bot_type_str = "Running Bot" if is_running else "Deployed Bot"
    
    text = (f"🤖 *Bot Panel*\n\n"
            f"👤 *Owner ID:* `{script_owner_id}`\n"
            f"📂 *File:* `{file_name}`\n"
            f"📅 *Uploaded on:* `{upload_time_str}`\n"
            f"🚦 *Status:* `{status_str}`{runtime_info}\n"
            f"⏳ *Subscription:* {sub_status}\n\n"
            f"Manage the bot using the controls below:")
    
    markup = create_control_buttons(script_owner_id, file_name, is_running, viewer_id=call.from_user.id)
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')

def start_bot_callback(call):
    parts = call.data.split('_')
    script_owner_id = int(parts[1])
    file_name = "_".join(parts[2:])
    
    if is_bot_running(script_owner_id, file_name):
        bot.answer_callback_query(call.id, "⚠️ This bot is already running!", show_alert=True)
        return
    
    if not is_user_admin(script_owner_id) and script_owner_id != OWNER_ID and get_active_bot_count(script_owner_id) >= get_active_bot_limit(script_owner_id):
        bot.answer_callback_query(call.id, f"⚠️ Limit reached ({get_active_bot_limit(script_owner_id)} active bot max). Stop your running bot first.", show_alert=True)
        return
    
    bot.answer_callback_query(call.id, "🚀 Starting bot...")
    user_folder = get_user_folder(script_owner_id)
    script_path = os.path.join(user_folder, file_name)
    
    file_ext = os.path.splitext(file_name)[1].lower()
    if file_ext == '.py':
        threading.Thread(target=run_script, args=(script_path, script_owner_id, user_folder, file_name, call.message)).start()
    elif file_ext == '.js':
        threading.Thread(target=run_js_script, args=(script_path, script_owner_id, user_folder, file_name, call.message)).start()
    
    time.sleep(1.5)
    call.data = f"file_{script_owner_id}_{file_name}"
    file_control_callback(call)

def stop_bot_callback(call):
    parts = call.data.split('_')
    script_owner_id = int(parts[1])
    file_name = "_".join(parts[2:])
    script_key = f"{script_owner_id}_{file_name}"
    
    if not is_bot_running(script_owner_id, file_name):
        bot.answer_callback_query(call.id, "⚠️ This bot is already stopped!", show_alert=True)
        return
    
    bot.answer_callback_query(call.id, "🛑 Stopping bot...")
    process_info = bot_scripts.get(script_key)
    if process_info:
        kill_process_tree(process_info)
        if script_key in bot_scripts:
            del bot_scripts[script_key]
    
    time.sleep(1)
    call.data = f"file_{script_owner_id}_{file_name}"
    file_control_callback(call)

def restart_bot_callback(call):
    parts = call.data.split('_')
    script_owner_id = int(parts[1])
    file_name = "_".join(parts[2:])
    script_key = f"{script_owner_id}_{file_name}"
    
    bot.answer_callback_query(call.id, "🔄 Restarting bot...")
    
    if is_bot_running(script_owner_id, file_name):
        process_info = bot_scripts.get(script_key)
        if process_info:
            kill_process_tree(process_info)
            if script_key in bot_scripts:
                del bot_scripts[script_key]
        time.sleep(1)
    
    user_folder = get_user_folder(script_owner_id)
    script_path = os.path.join(user_folder, file_name)
    file_ext = os.path.splitext(file_name)[1].lower()
    
    if file_ext == '.py':
        threading.Thread(target=run_script, args=(script_path, script_owner_id, user_folder, file_name, call.message)).start()
    elif file_ext == '.js':
        threading.Thread(target=run_js_script, args=(script_path, script_owner_id, user_folder, file_name, call.message)).start()
    
    time.sleep(1.5)
    call.data = f"file_{script_owner_id}_{file_name}"
    file_control_callback(call)

def delete_bot_callback(call):
    parts = call.data.split('_')
    script_owner_id = int(parts[1])
    file_name = "_".join(parts[2:])
    script_key = f"{script_owner_id}_{file_name}"
    
    bot.answer_callback_query(call.id, "🗑️ Deleting file...")
    
    if is_bot_running(script_owner_id, file_name):
        process_info = bot_scripts.get(script_key)
        if process_info:
            kill_process_tree(process_info)
            if script_key in bot_scripts:
                del bot_scripts[script_key]
        time.sleep(1)
    
    user_folder = get_user_folder(script_owner_id)
    file_path = os.path.join(user_folder, file_name)
    log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
    
    if os.path.exists(file_path):
        try: os.remove(file_path)
        except Exception: pass
    
    if os.path.exists(log_path):
        try: os.remove(log_path)
        except Exception: pass
    
    # Persistent Sync: Delete from Database
    relative_path = os.path.relpath(file_path, user_folder)
    delete_file_from_db(script_owner_id, relative_path)
    
    remove_user_file_db(script_owner_id, file_name)
    bot.answer_callback_query(call.id, f"✅ {file_name} deleted successfully!", show_alert=True)
    
    show_my_bot_status(call.message.chat.id, script_owner_id, call.message.message_id)

def logs_bot_callback(call):
    parts = call.data.split('_')
    script_owner_id = int(parts[1])
    file_name = "_".join(parts[2:])
    bot.answer_callback_query(call.id, "📜 Fetching logs...")
    
    user_folder = get_user_folder(script_owner_id)
    log_filename = f"{os.path.splitext(file_name)[0]}.log"
    log_path = os.path.join(user_folder, log_filename)
    
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                log_content = f.read()
            
            if not log_content.strip():
                log_content = "(Log file is empty)"
            
            if len(log_content) > 3500:
                log_content = log_content[-3500:] + "\n... (truncated)"
            
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("🔄 Refresh Logs", callback_data=f"logs_{script_owner_id}_{file_name}"),
                types.InlineKeyboardButton("📥 Download Log File", callback_data=f"viewlog_{script_owner_id}_{log_filename}")
            )
            markup.row(
                types.InlineKeyboardButton("🔙 Back to Control Panel", callback_data=f"file_{script_owner_id}_{file_name}")
            )
            
            bot.edit_message_text(f"📜 *Logs for* `{file_name}`:\n\n```\n{log_content}\n```", 
                                   call.message.chat.id, call.message.message_id, 
                                   reply_markup=markup, parse_mode='Markdown')
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error reading logs: {e}", show_alert=True)
    else:
        bot.answer_callback_query(call.id, "⚠️ Log file not found yet. Has the bot run?", show_alert=True)

def speed_callback(call):
    bot.answer_callback_query(call.id)
    _logic_bot_speed(call.message, sender_id=call.from_user.id)

def back_to_main_callback(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    user_username = call.from_user.username
    
    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
    expiry_info = ""
    balance = get_balance(user_id)
    
    if user_id == OWNER_ID: 
        user_status = "👑 Owner"
    elif is_user_admin(user_id): 
        user_status = "🛡️ Admin"
    elif user_id in user_subscriptions:
        expiry_date = user_subscriptions[user_id].get('expiry')
        if expiry_date and expiry_date > datetime.now():
            user_status = "Subscriber"
            days_left = (expiry_date - datetime.now()).days
            expiry_info = f"\n⏳ Expiry Time: {days_left} days remaining"
        else: 
            user_status = "Non-Subscriber"
            remove_subscription_db(user_id)
    else: 
        user_status = "Non-Subscriber"

    welcome_msg_text = (f"💠 <b>WELCOME TO MINO BOT HOSTING</b> 💠\n"
                        f"────────────────────────\n"
                        f"👤 <b>USER ID:</b> <code>{user_id}</code>\n"
                        f"✳️ <b>USERNAME:</b> <code>@{user_username or 'Not set'}</code>\n"
                        f"💵 <b>YOUR BALANCE:</b> <code>{balance:.2f} Tk</code>\n"
                        f"🔰 <b>STATUS:</b> <code>{user_status}</code>{expiry_info}\n"
                        f"📂 <b>FILES UPLOADED:</b> <code>{current_files} / {limit_str}</code>\n"
                        f"────────────────────────\n"
                        f"🤖 You can host and run Python (<code>.py</code>) and JavaScript (<code>.js</code>) scripts smoothly in real-time.\n\n"
                        f"👇 Use the menu buttons below to access your desired services.")
    
    bot.edit_message_text(welcome_msg_text, call.message.chat.id, call.message.message_id, 
                           reply_markup=create_reply_keyboard_main_menu(user_id), parse_mode='HTML')

def stats_callback(call):
    bot.answer_callback_query(call.id)
    _logic_statistics(call.message, sender_id=call.from_user.id)

def run_all_scripts_callback(call):
    bot.answer_callback_query(call.id)
    _logic_run_all_scripts(call)

def broadcast_init_callback(call):
    bot.answer_callback_query(call.id)
    _logic_broadcast_init(call.message, sender_id=call.from_user.id)

def admin_panel_callback(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_text("👑 *Admin Panel*\nManage admins, subscriptions, balances, and global settings below.", 
                           call.message.chat.id, call.message.message_id, 
                           reply_markup=create_admin_panel(), parse_mode='Markdown')

def subscription_management_callback(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_text("💳 *Subscription Management*\nAdd, remove, or verify active subscriber tiers:", 
                           call.message.chat.id, call.message.message_id, 
                           reply_markup=create_subscription_menu(), parse_mode='Markdown')

def add_admin_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "➕ *Add Admin*\nPlease enter the Telegram User ID of the new admin:")
    bot.register_next_step_handler(msg, process_add_admin)

def process_add_admin(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "⚠️ Owner only.")
        return
    try:
        admin_id = int(message.text.strip())
        add_admin_db(admin_id)
        bot.reply_to(message, f"✅ Successfully added `{admin_id}` as Admin.", parse_mode='Markdown')
    except Exception:
        bot.reply_to(message, "⚠️ Invalid User ID.")

def remove_admin_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "➖ *Remove Admin*\nPlease enter the Telegram User ID of the admin to remove:")
    bot.register_next_step_handler(msg, process_remove_admin)

def process_remove_admin(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "⚠️ Owner only.")
        return
    try:
        admin_id = int(message.text.strip())
        if remove_admin_db(admin_id):
            bot.reply_to(message, f"✅ Successfully removed `{admin_id}` from Admins.", parse_mode='Markdown')
        else:
            bot.reply_to(message, f"❌ Failed. `{admin_id}` not found or is the Owner.", parse_mode='Markdown')
    except Exception:
        bot.reply_to(message, "⚠️ Invalid User ID.")

def list_admins_callback(call):
    bot.answer_callback_query(call.id)
    admins_list = "\n".join([f"• `{aid}`" for aid in admin_ids])
    bot.edit_message_text(f"📋 *Admins List:*\n\n{admins_list}", 
                           call.message.chat.id, call.message.message_id, 
                           reply_markup=create_admin_panel(), parse_mode='Markdown')

def send_inbox_msg_init(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📬 *Direct Inbox Message*\nEnter target ID and message separated by `|` (e.g. `1234567 | Hello`):")
    bot.register_next_step_handler(msg, process_send_inbox_msg)

def process_send_inbox_msg(message):
    if not is_user_admin(message.from_user.id):
        return
    try:
        parts = message.text.split('|', 1)
        target_id = int(parts[0].strip())
        msg_text = parts[1].strip()
        bot.send_message(target_id, f"📬 *Message from Admin:*\n\n{msg_text}", parse_mode='Markdown')
        bot.reply_to(message, "✅ Direct message delivered successfully.")
    except Exception as e:
        bot.reply_to(message, f"❌ Failed. Error: {e}")

# --- Limit 10 Active Bot Helper Action Handlers ---
def stop_current_bot_callback(call):
    user_id = int(call.data.split('_')[3])
    bot.answer_callback_query(call.id, "⏹️ Stopping bot...")
    
    user_files_list = user_files.get(user_id, [])
    for file_name, file_type in user_files_list:
        script_key = f"{user_id}_{file_name}"
        if is_bot_running(user_id, file_name):
            process_info = bot_scripts.get(script_key)
            if process_info:
                kill_process_tree(process_info)
                del bot_scripts[script_key]
                
    bot.edit_message_text("✅ Your active running bots have been stopped. Now click *🚀 Deploy Bot* button to deploy a new one.", call.message.chat.id, call.message.message_id, reply_markup=None, parse_mode='Markdown')

def delete_current_bot_callback(call):
    user_id = int(call.data.split('_')[3])
    bot.answer_callback_query(call.id, "🗑️ Deleting files...")
    
    user_files_list = list(user_files.get(user_id, []))
    user_folder = get_user_folder(user_id)
    
    for file_name, file_type in user_files_list:
        script_key = f"{user_id}_{file_name}"
        if is_bot_running(user_id, file_name):
            process_info = bot_scripts.get(script_key)
            if process_info:
                kill_process_tree(process_info)
                del bot_scripts[script_key]
        
        file_path = os.path.join(user_folder, file_name)
        log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except Exception: pass
        if os.path.exists(log_path):
            try: os.remove(log_path)
            except Exception: pass
            
        remove_user_file_db(user_id, file_name)
    
    # Persistent Sync: Clear all file records of this user from DB
    delete_all_user_files_from_db(user_id)
        
    bot.edit_message_text("✅ All active files deleted. Now click *🚀 Deploy Bot* button to deploy a fresh bot with a new name.", call.message.chat.id, call.message.message_id, reply_markup=None, parse_mode='Markdown')

def replace_current_bot_direct_callback(call):
    user_id = int(call.data.split('_')[4])
    bot.answer_callback_query(call.id, "🔄 Stop active processes to replace...")
    
    user_files_list = list(user_files.get(user_id, []))
    user_folder = get_user_folder(user_id)
    
    for file_name, file_type in user_files_list:
        script_key = f"{user_id}_{file_name}"
        if is_bot_running(user_id, file_name):
            process_info = bot_scripts.get(script_key)
            if process_info:
                kill_process_tree(process_info)
                del bot_scripts[script_key]
        
        file_path = os.path.join(user_folder, file_name)
        log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except Exception: pass
        if os.path.exists(log_path):
            try: os.remove(log_path)
            except Exception: pass
            
        remove_user_file_db(user_id, file_name)
    
    # Persistent Sync: Clear all file records of this user from DB
    delete_all_user_files_from_db(user_id)
        
    bot.delete_message(call.message.chat.id, call.message.message_id)
    
    msg = bot.send_message(call.message.chat.id, "🏷️ *Please enter a name for your replacement Bot Project:*", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_bot_name_input)

# --- Broadcast Logic Implementation ---
def process_broadcast_message(message):
    user_id = message.from_user.id
    if not is_user_admin(user_id):
        return
    if message.text and message.text.lower() == '/cancel':
        bot.reply_to(message, "❌ Broadcast cancelled.")
        return
    
    broadcast_text = message.text
    pending_broadcasts[user_id] = broadcast_text
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Confirm Broadcast", callback_data=f"confirm_broadcast_{user_id}"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_broadcast")
    )
    bot.reply_to(message, f"📢 *Are you sure you want to broadcast this message to all users?*\n\n{broadcast_text}", reply_markup=markup, parse_mode='Markdown')

def handle_confirm_broadcast(call):
    admin_id = int(call.data.replace('confirm_broadcast_', ''))
    bot.answer_callback_query(call.id)
    
    broadcast_text = pending_broadcasts.get(admin_id)
    if not broadcast_text:
        bot.send_message(call.message.chat.id, "❌ No pending broadcast found.")
        return
    
    bot.edit_message_text("📤 Dispatching broadcast to all active users...", call.message.chat.id, call.message.message_id)
    
    success_count = 0
    fail_count = 0
    for uid in list(active_users):
        try:
            bot.send_message(uid, f"📢 *Important Broadcast Notice:*\n\n{broadcast_text}", parse_mode='Markdown')
            success_count += 1
            time.sleep(0.05) 
        except Exception:
            fail_count += 1
            
    bot.send_message(call.message.chat.id, f"✅ Broadcast finished!\n\n🟢 Successful: {success_count}\n🔴 Failed: {fail_count}")
    if admin_id in pending_broadcasts:
        del pending_broadcasts[admin_id]

def handle_cancel_broadcast(call):
    bot.answer_callback_query(call.id, "Broadcast cancelled.")
    bot.edit_message_text("❌ Broadcast cancelled by Admin.", call.message.chat.id, call.message.message_id)

# --- Subscription Init/Actions Management ---
def add_subscription_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "➕ Enter User ID and Days separated by `|` (e.g. `1234567 | 30`):")
    bot.register_next_step_handler(msg, process_add_subscription)

def process_add_subscription(message):
    if not is_user_admin(message.from_user.id):
        return
    try:
        parts = message.text.split('|')
        target_id = int(parts[0].strip())
        days = int(parts[1].strip())
        
        current_expiry = user_subscriptions.get(target_id, {}).get('expiry')
        new_expiry = calculate_fair_expiry(days, current_expiry)
        save_subscription(target_id, new_expiry)
        
        bot.reply_to(message, f"✅ Subscription of `{days} Days` successfully added to User: `{target_id}`.\n📅 Expiry: `{new_expiry}`", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Failed. Use correct format `User_ID | Days`.\nError: {e}")

def remove_subscription_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "➖ Enter User ID to remove subscription:")
    bot.register_next_step_handler(msg, process_remove_subscription)

def process_remove_subscription(message):
    if not is_user_admin(message.from_user.id):
        return
    try:
        target_id = int(message.text.strip())
        remove_subscription_db(target_id)
        bot.reply_to(message, f"✅ Subscription removed for User: `{target_id}`", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Failed. Error: {e}")

def check_subscription_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "🔍 Enter User ID to verify subscription details:")
    bot.register_next_step_handler(msg, process_check_subscription)

def process_check_subscription(message):
    if not is_user_admin(message.from_user.id):
        return
    try:
        target_id = int(message.text.strip())
        expiry = user_subscriptions.get(target_id, {}).get('expiry')
        if expiry:
            if expiry > datetime.now():
                days_left = (expiry - datetime.now()).days
                bot.reply_to(message, f"🟢 User `{target_id}` has an Active Premium Subscription.\n⏳ Remaining: `{days_left} Days` (Expiry: `{expiry}`)", parse_mode='Markdown')
            else:
                bot.reply_to(message, f"🔴 User `{target_id}` subscription has expired on `{expiry}`", parse_mode='Markdown')
        else:
            bot.reply_to(message, f"❌ User `{target_id}` has no active subscription record.", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Failed. Error: {e}")

# --- Command & Log Callback Mappings ---
def send_command_callback(call):
    bot.answer_callback_query(call.id)
    _logic_send_command(call.message)

def send_to_process_callback(call):
    bot.answer_callback_query(call.id)
    send_to_process_init(call.message)

def sendcmd_select_callback(call):
    script_key = call.data.replace('sendcmd_select_', '')
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, f"📝 Enter command to send to `{script_key}`:")
    bot.register_next_step_handler(msg, lambda m: process_send_command(m, script_key))

def view_all_logs_callback(call):
    bot.answer_callback_query(call.id)
    view_all_logs(call.message)

def viewlog_callback(call):
    bot.answer_callback_query(call.id)
    parts = call.data.split('_')
    target_id = int(parts[1])
    log_file = "_".join(parts[2:])
    user_folder = get_user_folder(target_id)
    log_path = os.path.join(user_folder, log_file)
    send_log_file(call.message, log_path, log_file)

def toggle_lock_admin_callback(call):
    bot.answer_callback_query(call.id)
    global bot_locked
    bot_locked = not bot_locked
    status = "locked" if bot_locked else "unlocked"
    bot.edit_message_text(f"🔒 Bot has been {status}.", call.message.chat.id, call.message.message_id)

def handle_buy_product(call):
    bot.answer_callback_query(call.id)
    buy_packages_list_callback(call)

# --- Admin View Code & Edit Code Systems ---
def adm_viewcode_callback(call):
    user_id = call.from_user.id
    if not is_user_admin(user_id):
        bot.answer_callback_query(call.id, "⚠️ Admins only.", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    
    parts = call.data.split('_')
    target_user_id = int(parts[2])
    file_name = "_".join(parts[3:])
    
    user_folder = get_user_folder(target_user_id)
    file_path = os.path.join(user_folder, file_name)
    
    if not os.path.exists(file_path):
        bot.send_message(call.message.chat.id, "❌ File not found on disk!")
        return
        
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        if not content.strip():
            content = "# (Empty File)"
        
        if len(content) <= 3500:
            bot.send_message(call.message.chat.id, f"📄 *Source code of `{file_name}`:*\n\n```python\n{content}\n```", parse_mode='Markdown')
        else:
            with open(file_path, 'rb') as doc_f:
                bot.send_document(call.message.chat.id, doc_f, caption=f"📄 *Full Source File:* `{file_name}`", parse_mode='Markdown')
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Error reading file: {e}")

def adm_editcode_callback(call):
    user_id = call.from_user.id
    if not is_user_admin(user_id):
        bot.answer_callback_query(call.id, "⚠️ Admins only.", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    
    parts = call.data.split('_')
    target_user_id = int(parts[2])
    file_name = "_".join(parts[3:])
    
    msg = bot.send_message(call.message.chat.id, f"✏️ *Editing file `{file_name}` of user `{target_user_id}`*\n\nPlease reply with the **New Source Code** or **Upload the new script file** to overwrite it:\nType `/cancel` to abort.", parse_mode='Markdown')
    bot.register_next_step_handler(msg, lambda m: process_adm_edit_code(m, target_user_id, file_name))
    
def process_adm_edit_code(message, target_user_id, file_name):
    if check_menu_intercept(message):
        return
    if message.text and message.text.strip().lower() == '/cancel':
        bot.reply_to(message, "❌ Editing cancelled.")
        return
        
    user_folder = get_user_folder(target_user_id)
    file_path = os.path.join(user_folder, file_name)
    
    try:
        if message.document:
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            with open(file_path, 'wb') as f:
                f.write(downloaded_file)
        elif message.text:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(message.text)
        else:
            bot.reply_to(message, "⚠️ Unsupported input type. Please send code text or upload a document.")
            return
        
        file_type = 'py' if file_name.endswith('.py') else 'js'
        
        # Persistent Sync: Save overwritten file to DB
        save_file_to_db(target_user_id, file_path)
        
        # Original File metadata registration
        save_user_file(target_user_id, file_name, file_type)
        
        script_key = f"{target_user_id}_{file_name}"
        is_running = is_bot_running(target_user_id, file_name)
        restart_status = ""
        if is_running:
            process_info = bot_scripts.get(script_key)
            if process_info:
                kill_process_tree(process_info)
                del bot_scripts[script_key]
            time.sleep(1)
            if file_type == 'py':
                threading.Thread(target=run_script, args=(file_path, target_user_id, user_folder, file_name, message)).start()
            elif file_type == 'js':
                threading.Thread(target=run_js_script, args=(file_path, target_user_id, user_folder, file_name, message)).start()
            restart_status = "\n\n🔄 Bot has been restarted automatically with the new code!"
        
        bot.reply_to(message, f"✅ Code for `{file_name}` edited successfully!{restart_status}", parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Failed to edit file. Error: {e}")

# --- Direct Callback Mapping Routing Hub ---
@bot.callback_query_handler(func=lambda call: True) 
def handle_callbacks(call):
    user_id = call.from_user.id
    data = call.data
    logger.info(f"Callback: User={user_id}, Data='{data}'")

    if bot_locked and not is_user_admin(user_id) and data not in ['back_to_main', 'back_to_service', 'speed', 'stats']:
        bot.answer_callback_query(call.id, "⚠️ Bot locked by admin.", show_alert=True)
        return
    try:
        if data == 'upload': upload_callback(call)
        elif data == 'check_files': check_files_callback(call)
        elif data.startswith('file_'): file_control_callback(call)
        elif data.startswith('start_'): start_bot_callback(call)
        elif data.startswith('stop_'): stop_bot_callback(call)
        elif data.startswith('restart_'): restart_bot_callback(call)
        elif data.startswith('delete_'): delete_bot_callback(call)
        elif data.startswith('logs_'): logs_bot_callback(call)
        elif data == 'speed': speed_callback(call)
        elif data == 'back_to_main' or data == 'back_to_service': back_to_main_callback(call)
        elif data.startswith('confirm_broadcast_'): handle_confirm_broadcast(call)
        elif data == 'cancel_broadcast': handle_cancel_broadcast(call)
        elif data == 'send_command': send_command_callback(call)
        elif data == 'send_to_process': send_to_process_callback(call)
        elif data.startswith('sendcmd_select_'): sendcmd_select_callback(call)
        elif data == 'view_all_logs': view_all_logs_callback(call)
        elif data.startswith('viewlog_'): viewlog_callback(call)
        elif data == 'balance_packages': show_balance_packages_menu(call, user_id)
        elif data == 'recharge_balance': recharge_balance_callback(call)
        elif data.startswith('paymethod_'): handle_paymethod_selection(call)
        elif data == 'buy_packages_list': buy_packages_list_callback(call)
        elif data.startswith('buy_pkg_'): handle_buy_pkg_callback(call)
        elif data.startswith('dep_'): handle_deposit_callback(call)
        elif data == 'buy_products_list': show_products_list(call, user_id)
        elif data.startswith('buy_prod_'): handle_buy_product(call)
        elif data == 'subscription': admin_required_callback(call, subscription_management_callback)
        elif data == 'stats': stats_callback(call)
        elif data == 'toggle_lock_admin': admin_required_callback(call, toggle_lock_admin_callback)
        elif data == 'run_all_scripts': admin_required_callback(call, run_all_scripts_callback)
        elif data == 'broadcast': admin_required_callback(call, broadcast_init_callback) 
        elif data == 'admin_panel': admin_required_callback(call, admin_panel_callback)
        elif data == 'add_admin': owner_required_callback(call, add_admin_init_callback) 
        elif data == 'remove_admin': owner_required_callback(call, remove_admin_init_callback) 
        elif data == 'list_admins': admin_required_callback(call, list_admins_callback)
        elif data == 'send_inbox_msg': admin_required_callback(call, send_inbox_msg_init)
        elif data == 'edit_bot_limits': admin_required_callback(call, edit_bot_limits_callback)
        elif data.startswith('modlimit_'): admin_required_callback(call, handle_modlimit_callback)
        elif data == 'add_subscription': admin_required_callback(call, add_subscription_init_callback) 
        elif data == 'remove_subscription': admin_required_callback(call, remove_subscription_init_callback) 
        elif data == 'check_subscription': admin_required_callback(call, check_subscription_init_callback) 
        elif data == 'admin_running_bots': admin_required_callback(call, admin_running_bots_callback)
        elif data == 'admin_manage_user': admin_required_callback(call, admin_manage_user_init)
        elif data.startswith('usermg_bal_'): admin_required_callback(call, usermg_bal_callback)
        elif data.startswith('usermg_addbal_'): admin_required_callback(call, usermg_addbal_callback)
        elif data.startswith('usermg_subbal_'): admin_required_callback(call, usermg_subbal_callback)
        elif data.startswith('usermg_setbal_'): admin_required_callback(call, usermg_setbal_callback)
        elif data.startswith('usermg_sub_'): admin_required_callback(call, usermg_sub_callback)
        elif data.startswith('usermg_rem_'): admin_required_callback(call, usermg_rem_callback)
        elif data.startswith('usermg_files_'): admin_required_callback(call, usermg_files_callback)
        elif data.startswith('admin_inspect_user_'): admin_required_callback(call, admin_inspect_user_callback)
        elif data == 'admin_edit_packages': admin_required_callback(call, admin_edit_packages_callback)
        elif data.startswith('admin_pkg_manage_'): admin_required_callback(call, admin_pkg_manage_callback)
        elif data.startswith('admin_pkg_name_'): admin_required_callback(call, admin_pkg_name_callback)
        elif data.startswith('admin_pkg_price_'): admin_required_callback(call, admin_pkg_price_callback)
        elif data.startswith('admin_pkg_days_'): admin_required_callback(call, admin_pkg_days_callback)
        elif data.startswith('admin_pkg_limit_'): admin_required_callback(call, admin_pkg_limit_callback)
        elif data == 'admin_pkg_add_init': admin_required_callback(call, admin_pkg_add_init_callback)
        elif data == 'admin_toggle_sales': admin_required_callback(call, admin_toggle_sales_callback)
        elif data == 'admin_toggle_recharge': admin_required_callback(call, admin_toggle_recharge_callback)
        elif data.startswith('stop_current_bot_') or data.startswith('stop_and_replace_menu_'): stop_current_bot_callback(call)
        elif data.startswith('delete_current_bot_') or data.startswith('delete_and_replace_menu_'): delete_current_bot_callback(call)
        elif data.startswith('replace_current_bot_direct_'): replace_current_bot_direct_callback(call)
        elif data.startswith('adm_viewcode_'): adm_viewcode_callback(call)
        elif data.startswith('adm_editcode_'): adm_editcode_callback(call)
        elif data == 'back_to_my_bot':
            bot.answer_callback_query(call.id)
            show_my_bot_status(call.message.chat.id, call.from_user.id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "Unknown action.")
    except Exception as e:
        logger.error(f"Error handling callback: {e}", exc_info=True)

# --- Button Routing Logic ---
BUTTON_TEXT_TO_LOGIC = {
    "🛍️ Products": lambda m: show_products_list(m, m.from_user.id),
    "💵 Balance": _logic_balance_packages,
    "💵 Recharge": lambda m: recharge_balance_command(m),
    "🚀 Deploy Bot": lambda m: _logic_check_files(m, sender_id=m.from_user.id),
    "🤖 My Bot": _logic_my_bot,
    "⚡ Bot Speed": lambda m: _logic_bot_speed(m, sender_id=m.from_user.id),
    "📊 Statistics": lambda m: _logic_statistics(m, sender_id=m.from_user.id),
    "👑 Admin Panel": _logic_admin_panel,
    "📞 Help & Support": _logic_contact_owner
}

@bot.message_handler(func=lambda message: message.text in BUTTON_TEXT_TO_LOGIC)
def handle_button_text(message):
    logic_func = BUTTON_TEXT_TO_LOGIC.get(message.text)
    if logic_func: logic_func(message)

# --- Commands Registration ---
@bot.message_handler(commands=['start'])
def command_start(message): _logic_send_welcome(message)
@bot.message_handler(commands=['uploadfile'])
def command_upload_file(message): _logic_upload_file(message, sender_id=message.from_user.id)
@bot.message_handler(commands=['checkfiles'])
def command_check_files(message): _logic_check_files(message, sender_id=message.from_user.id)
@bot.message_handler(commands=['botspeed'])
def command_bot_speed(message): _logic_bot_speed(message, sender_id=message.from_user.id)
@bot.message_handler(commands=['sendcommand'])
def command_send_command(message): _logic_send_command(message)
@bot.message_handler(commands=['contactowner'])
def command_contact_owner(message): _logic_contact_owner(message)
@bot.message_handler(commands=['subscriptions'])
def command_subscriptions(message): _logic_subscriptions_panel(message)
@bot.message_handler(commands=['statistics'])
def command_statistics(message): _logic_statistics(message, sender_id=message.from_user.id)
@bot.message_handler(commands=['broadcast'])
def command_broadcast(message): _logic_broadcast_init(message, sender_id=message.from_user.id)
@bot.message_handler(commands=['lockbot']) 
def command_lock_bot(message): _logic_toggle_lock_bot(message)
@bot.message_handler(commands=['adminpanel'])
def command_admin_panel(message): _logic_admin_panel(message)
@bot.message_handler(commands=['runningallcode'])
def command_run_all_code(message): _logic_run_all_scripts(message)
@bot.message_handler(commands=['restart'])
def command_restart_main(message):
    user_id = message.from_user.id
    if user_id != OWNER_ID:
        bot.reply_to(message, "⚠️ Only the Owner can restart the main bot.")
        return
    
    bot.reply_to(message, "🔄 *Restarting main bot server...* Please wait.", parse_mode='Markdown')
    logger.warning("Restart command received. Performing graceful shutdown and restart.")
    
    cleanup()
    
    os.execv(sys.executable, [sys.executable] + sys.argv)

@bot.message_handler(commands=['ping'])
def ping(message):
    start_ping_time = time.time() 
    msg = bot.reply_to(message, "Pong!")
    latency = round((time.time() - start_ping_time) * 1000, 2)
    bot.edit_message_text(f"Pong! Latency: {latency} ms", message.chat.id, msg.message_id)

# --- Shutdown Cleanup Function ---
def cleanup():
    logger.warning("Shutdown. Cleaning up processes...")
    script_keys_to_stop = list(bot_scripts.keys()) 
    if not script_keys_to_stop: return
    for key in script_keys_to_stop:
        if key in bot_scripts: kill_process_tree(bot_scripts[key])
atexit.register(cleanup)

# --- Main Execution ---
if __name__ == '__main__':
    logger.info("="*40 + "\n🤖 Bot Starting Up...\n" + f"🐍 Python: {sys.version.split()[0]}\n" +
                f"🔧 Base Dir: {BASE_DIR}\n📁 Upload Dir: {UPLOAD_BOTS_DIR}\n" +
                f"📊 Data Dir: {IROTECH_DIR}\n🔑 Owner ID: {OWNER_ID}\n" + "="*40)
    
    keep_alive()
    
    logger.info("🚀 Starting polling...")
    while True:
        try:
            bot.infinity_polling(logger_level=logging.INFO, timeout=60, long_polling_timeout=30)
        except Exception as e:
            logger.critical(f"Critical error: {e}", exc_info=True)
            time.sleep(10)
