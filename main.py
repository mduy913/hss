
import os
import time
import json
import random
import string
import threading
import logging
import secrets

import requests
import telebot

from flask import Flask, request, jsonify
from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)

# ==================================================
# CONFIGURATION
# ==================================================

BOT_TOKEN = "8314558446:AAFGz92fVeLdomzfN0EeNZk-HFtDSC8hHEg"
LINK4M_TOKEN = "699ac288bb556c3eae114a58"
RENDER_URL = "https://voice-mleh.onrender.com" 
FIREBASE_URL = "https://shopmduy-default-rtdb.asia-southeast1.firebasedatabase.app/"
OTP_EXPIRE = 300
REQUEST_TIMEOUT = 20

# ==================================================
# INITIALIZATION
# ==================================================

if not BOT_TOKEN or not LINK4M_TOKEN:
    raise RuntimeError("Missing BOT_TOKEN or LINK4M_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

log = logging.getLogger("MDUYK")

ADMIN_ID = None

USER_SESSIONS = {}
OTP_CODES = {}

SESSION_LOCK = threading.RLock()
OTP_LOCK = threading.RLock()

# ==================================================
# FIREBASE
# ==================================================

def firebase_request(method, path, data=None):
    url = FIREBASE_URL + path.lstrip("/") + ".json"

    response = requests.request(
        method,
        url,
        json=data,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    if not response.text:
        return None

    return response.json()


def get_products():
    try:
        return firebase_request("GET", "products") or {}
    except Exception:
        log.exception("GET PRODUCTS ERROR")
        return {}


def get_admin():
    try:
        return firebase_request("GET", "admin_id")
    except Exception:
        log.exception("GET ADMIN ERROR")
        return None


def is_admin(user_id):
    global ADMIN_ID

    if ADMIN_ID is None:
        ADMIN_ID = get_admin()

    return str(user_id) == str(ADMIN_ID)


def save_product(name, links):
    if not name or "/" in name or "." in name or "#" in name:
        raise ValueError("Tên sản phẩm không hợp lệ")

    firebase_request(
        "PATCH",
        f"products/{name}",
        {
            "links_required": links
        }
    )


def add_acc_to_db(name, username, password):
    firebase_request(
        "POST",
        f"products/{name}/stock",
        {
            "user": username,
            "pass": password
        }
    )


def get_stock_count(name):
    stock = firebase_request(
        "GET",
        f"products/{name}/stock"
    )

    return len(stock) if isinstance(stock, dict) else 0


def get_and_remove_acc(name):
    """
    Đọc và xóa tài khoản bằng ETag để tránh
    hai người nhận cùng một tài khoản.
    """
    url = FIREBASE_URL + f"products/{name}/stock.json"

    response = requests.get(
        url,
        headers={"X-Firebase-ETag": "true"},
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    stock = response.json()

    if not isinstance(stock, dict) or not stock:
        return None

    key = next(iter(stock))
    acc = stock[key]
    etag = response.headers.get("ETag")

    if not etag:
        raise RuntimeError("Firebase không trả ETag")

    delete_response = requests.delete(
        url,
        params={"print": "silent"},
        headers={"If-Match": etag},
        timeout=REQUEST_TIMEOUT
    )

    if delete_response.status_code == 412:
        return None

    delete_response.raise_for_status()

    return acc


# ==================================================
# LINK4M
# ==================================================

def create_short_link(target_url):
    try:
        response = requests.get(
            "https://link4m.co/api-shorten/v2",
            params={
                "api": LINK4M_TOKEN,
                "url": target_url
            },
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()

        data = response.json()

        log.info("LINK4M STATUS: %s", data.get("status"))

        if data.get("status") != "success":
            log.error("LINK4M ERROR: %s", data)
            return None

        short_url = data.get("shortenedUrl")

        if not isinstance(short_url, str):
            return None

        if not short_url.startswith("https://"):
            return None

        return short_url

    except Exception:
        log.exception("CREATE SHORT LINK ERROR")
        return None


# ==================================================
# SESSION
# ==================================================

def create_session(chat_id, product):
    token = secrets.token_urlsafe(24)

    session = {
        "product": product,
        "links_done": 0,
        "links_required": 0,
        "token": token
    }

    with SESSION_LOCK:
        USER_SESSIONS[chat_id] = session

    return token


def clear_session(chat_id):
    with SESSION_LOCK:
        USER_SESSIONS.pop(chat_id, None)


def create_otp(chat_id, product):
    otp = ''.join(
        random.choices(string.digits, k=6)
    )

    with OTP_LOCK:
        while otp in OTP_CODES:
            otp = ''.join(
                random.choices(string.digits, k=6)
            )

        OTP_CODES[otp] = {
            "chat_id": chat_id,
            "product": product,
            "expires": time.time() + OTP_EXPIRE
        }

    return otp


# ==================================================
# WEBHOOK TELEGRAM
# ==================================================

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def receive_update():
    try:
        if not request.is_json:
            return "Invalid content", 403

        update = telebot.types.Update.de_json(
            request.get_json()
        )

        bot.process_new_updates([update])

        return "OK", 200

    except Exception:
        log.exception("TELEGRAM WEBHOOK ERROR")
        return "ERROR", 500


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "online",
        "bot": "MDUYK"
    })


# ==================================================
# LINK4M CALLBACK
# ==================================================

@app.route(
    "/callback/<int:chat_id>/<token>",
    methods=["GET"]
)
def link4m_callback(chat_id, token):

    with SESSION_LOCK:
        session = USER_SESSIONS.get(chat_id)

        if not session:
            return "Session expired", 404

        if not secrets.compare_digest(
            str(session["token"]),
            str(token)
        ):
            return "Invalid token", 403

        session["links_done"] += 1

        done = session["links_done"]
        required = session["links_required"]
        product = session["product"]

    try:
        if done >= required:

            otp = create_otp(chat_id, product)
            clear_session(chat_id)

            bot.send_message(
                chat_id,
                "🎉 VƯỢT LINK THÀNH CÔNG!\n\n"
                f"Sản phẩm: {product}\n"
                f"OTP: {otp}\n\n"
                "Sử dụng lệnh:\n"
                f"/claim {otp}\n\n"
                "OTP có hiệu lực trong 5 phút."
            )

            return "Completed", 200

        with SESSION_LOCK:
            current = USER_SESSIONS.get(chat_id)

        if not current:
            return "Session expired", 404

        target_url = (
            f"{RENDER_URL}/callback/{chat_id}/{token}"
        )

        short_url = create_short_link(target_url)

        if not short_url:
            return "Link creation failed", 503

        markup = InlineKeyboardMarkup()

        markup.add(
            InlineKeyboardButton(
                f"👉 VƯỢT LINK {done + 1}/{required}",
                url=short_url
            )
        )

        bot.send_message(
            chat_id,
            f"✅ Đã hoàn thành {done}/{required} link!\n"
            f"Còn {required - done} link.",
            reply_markup=markup
        )

        return "OK", 200

    except Exception:
        log.exception("LINK CALLBACK ERROR")
        return "ERROR", 500


# ==================================================
# START
# ==================================================

@bot.message_handler(commands=["start"])
def send_welcome(message):

    global ADMIN_ID

    chat_id = message.chat.id

    saved_admin = get_admin()

    if saved_admin is None:

        try:
            firebase_request(
                "PUT",
                "admin_id",
                chat_id
            )

            ADMIN_ID = chat_id

            bot.send_message(
                chat_id,
                "👑 Bạn là ADMIN đầu tiên!\n"
                "Dùng /admin để xem quyền."
            )

        except Exception:
            log.exception("ADMIN INITIALIZATION ERROR")

            bot.send_message(
                chat_id,
                "Không thể khởi tạo Admin."
            )

        return

    ADMIN_ID = saved_admin

    if is_admin(chat_id):
        bot.send_message(
            chat_id,
            "👑 CHÀO ADMIN MDUYK!\n"
            "Dùng /admin để xem chức năng."
        )
        return

    markup = ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    markup.add(
        KeyboardButton("🛒 CHỌN SẢN PHẨM")
    )

    bot.send_message(
        chat_id,
        "🎁 CHÀO MỪNG ĐẾN VỚI MDUYK SHOP!\n\n"
        "Bấm nút bên dưới để chọn sản phẩm.",
        reply_markup=markup
    )


# ==================================================
# ADMIN
# ==================================================

@bot.message_handler(commands=["admin"])
def admin_panel(message):

    if not is_admin(message.chat.id):
        return

    bot.send_message(
        message.chat.id,
        "👑 ADMIN MDUYK\n\n"
        "/add_prod Tên SP | số link\n"
        "/add_acc Tên SP | user | pass\n"
        "/products - Danh sách sản phẩm\n"
        "/stock - Kiểm tra kho"
    )


@bot.message_handler(commands=["add_prod"])
def add_prod(message):

    if not is_admin(message.chat.id):
        return

    try:
        raw = message.text.partition(" ")[2]

        name, links = raw.rsplit("|", 1)

        name = name.strip()
        links = int(links.strip())

        if links < 1 or links > 20:
            raise ValueError("Số link từ 1 đến 20")

        save_product(name, links)

        bot.reply_to(
            message,
            f"✅ Đã thêm sản phẩm: {name}\n"
            f"Số link: {links}"
        )

    except Exception as e:

        bot.reply_to(
            message,
            "❌ Không thể thêm sản phẩm.\n"
            "Ví dụ: /add_prod VIP | 2\n"
            f"Lỗi: {str(e)}"
        )


@bot.message_handler(commands=["add_acc"])
def add_acc(message):

    if not is_admin(message.chat.id):
        return

    try:
        raw = message.text.partition(" ")[2]

        name, username, password = raw.split("|", 2)

        name = name.strip()
        username = username.strip()
        password = password.strip()

        products = get_products()

        if name not in products:
            raise ValueError("Sản phẩm không tồn tại")

        if not username or not password:
            raise ValueError("Thiếu username hoặc password")

        add_acc_to_db(
            name,
            username,
            password
        )

        bot.reply_to(
            message,
            f"✅ Đã thêm tài khoản vào {name}"
        )

    except Exception as e:

        bot.reply_to(
            message,
            "❌ Lỗi thêm tài khoản.\n"
            "Ví dụ: /add_acc VIP | user1 | pass1\n"
            f"Lỗi: {str(e)}"
        )


@bot.message_handler(commands=["products"])
def admin_products(message):

    if not is_admin(message.chat.id):
        return

    products = get_products()

    if not products:
        bot.send_message(
            message.chat.id,
            "Chưa có sản phẩm."
        )
        return

    lines = ["📦 DANH SÁCH SẢN PHẨM"]

    for name, data in products.items():

        links = data.get("links_required", 0)

        lines.append(
            f"\n🎁 {name}\n"
            f"Link cần vượt: {links}"
        )

    bot.send_message(
        message.chat.id,
        "\n".join(lines)
    )


@bot.message_handler(commands=["stock"])
def admin_stock(message):

    if not is_admin(message.chat.id):
        return

    products = get_products()

    lines = ["📦 KHO TÀI KHOẢN"]

    for name in products:

        try:
            count = get_stock_count(name)

            lines.append(
                f"\n{name}: {count} tài khoản"
            )

        except Exception:
            lines.append(
                f"\n{name}: Không thể kiểm tra"
            )

    bot.send_message(
        message.chat.id,
        "\n".join(lines)
    )


# ==================================================
# CLAIM
# ==================================================

@bot.message_handler(commands=["claim"])
def claim_acc(message):

    chat_id = message.chat.id

    try:
        otp = message.text.partition(" ")[2].strip()

        if not otp:
            raise ValueError("Thiếu OTP")

        with OTP_LOCK:
            session = OTP_CODES.get(otp)

            if not session:
                raise ValueError("OTP không hợp lệ")

            if session["chat_id"] != chat_id:
                raise PermissionError("OTP không thuộc về bạn")

            if time.time() > session["expires"]:
                del OTP_CODES[otp]
                raise TimeoutError("OTP đã hết hạn")

            # Đánh dấu đang xử lý để tránh claim đồng thời
            del OTP_CODES[otp]

        product = session["product"]

        acc = get_and_remove_acc(product)

        if not acc:
            bot.reply_to(
                message,
                "❌ Kho đã hết tài khoản!\n"
                "Vui lòng liên hệ Admin."
            )
            return

        bot.reply_to(
            message,
            "🎁 TÀI KHOẢN CỦA BẠN:\n\n"
            f"{acc.get('user', '')} | "
            f"{acc.get('pass', '')}\n\n"
            "Cảm ơn bạn đã sử dụng MDUYK SHOP!"
        )

    except PermissionError:
        bot.reply_to(
            message,
            "❌ OTP không thuộc về bạn."
        )

    except TimeoutError:
        bot.reply_to(
            message,
            "❌ OTP đã hết hạn."
        )

    except ValueError:
        bot.reply_to(
            message,
            "❌ OTP không hợp lệ hoặc đã sử dụng."
        )

    except Exception:
        log.exception("CLAIM ERROR")

        bot.reply_to(
            message,
            "❌ Lỗi nhận tài khoản. Liên hệ Admin."
        )


# ==================================================
# PRODUCT LIST
# ==================================================

@bot.message_handler(
    func=lambda message: message.text == "🛒 CHỌN SẢN PHẨM"
)
def list_products(message):

    products = get_products()

    if not products:
        bot.send_message(
            message.chat.id,
            "Hiện tại chưa có sản phẩm nào!"
        )
        return

    markup = InlineKeyboardMarkup()

    for name in products:

        markup.add(
            InlineKeyboardButton(
                f"🎁 {name}",
                callback_data=f"buy_{name}"
            )
        )

    bot.send_message(
        message.chat.id,
        "🎁 VUI LÒNG CHỌN SẢN PHẨM:",
        reply_markup=markup
    )


# ==================================================
# BUY PRODUCT
# ==================================================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("buy_")
)
def buy_product(call):

    chat_id = call.message.chat.id

    try:
        bot.answer_callback_query(
            call.id,
            "Đang tạo link..."
        )

        product = call.data.partition("_")[2]

        with SESSION_LOCK:
            if chat_id in USER_SESSIONS:
                bot.send_message(
                    chat_id,
                    "⚠️ Bạn đang có nhiệm vụ chưa hoàn thành!"
                )
                return

        products = get_products()

        if product not in products:
            bot.send_message(
                chat_id,
                "❌ Sản phẩm không tồn tại!"
            )
            return

        links = int(
            products[product].get("links_required", 0)
        )

        if links < 1:
            bot.send_message(
                chat_id,
                "❌ Sản phẩm chưa cấu hình link!"
            )
            return

        if get_stock_count(product) < 1:
            bot.send_message(
                chat_id,
                "❌ Sản phẩm hiện đã hết hàng!"
            )
            return

        token = secrets.token_urlsafe(24)

        target_url = (
            f"{RENDER_URL}/callback/{chat_id}/{token}"
        )

        short_url = create_short_link(target_url)

        if not short_url:
            bot.send_message(
                chat_id,
                "❌ Link4M không thể tạo link!\n"
                "Vui lòng thử lại sau."
            )
            return

        with SESSION_LOCK:

            if chat_id in USER_SESSIONS:
                bot.send_message(
                    chat_id,
                    "Bạn đã có nhiệm vụ đang chạy."
                )
                return

            USER_SESSIONS[chat_id] = {
                "product": product,
                "links_done": 0,
                "links_required": links,
                "token": token
            }

        markup = InlineKeyboardMarkup()

        markup.add(
            InlineKeyboardButton(
                f"👉 VƯỢT LINK 1/{links}",
                url=short_url
            )
        )

        bot.send_message(
            chat_id,
            f"🎁 SẢN PHẨM: {product}\n\n"
            f"🔗 Tổng link: {links}\n"
            "✅ Tiến độ: 0/{0}".format(links) +
            "\n\nBấm nút dưới để bắt đầu.",
            reply_markup=markup
        )

        log.info(
            "BUY SUCCESS user=%s product=%s",
            chat_id,
            product
        )

    except Exception:

        log.exception("BUY PRODUCT ERROR")

        clear_session(chat_id)

        bot.send_message(
            chat_id,
            "❌ Có lỗi khi tạo link. Vui lòng thử lại."
        )


# ==================================================
# CLEAN EXPIRED OTP
# ==================================================

def cleanup_expired_otp():

    while True:

        time.sleep(30)

        now = time.time()

        with OTP_LOCK:

            expired = [
                otp
                for otp, data in OTP_CODES.items()
                if now > data["expires"]
            ]

            for otp in expired:
                del OTP_CODES[otp]


# ==================================================
# START SERVER
# ==================================================

def start_bot():

    bot.remove_webhook()

    time.sleep(2)

    bot.set_webhook(
        url=f"{RENDER_URL}/{BOT_TOKEN}"
    )

    log.info("Telegram webhook configured")


if __name__ == "__main__":

    threading.Thread(
        target=cleanup_expired_otp,
        daemon=True
    ).start()

    start_bot()

    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "3000")),
        debug=False
    )
