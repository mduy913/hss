import os
import time
import html
import base64
import secrets
import string
import threading
import logging

import requests
import telebot

from flask import Flask
from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)

# ==================================================
# CẤU HÌNH
# ==================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
LINK4M_TOKEN = os.getenv("LINK4M_TOKEN", "")

RENDER_URL = os.getenv(
    "RENDER_URL",
    "https://voice-mleh.onrender.com"
).rstrip("/")

FIREBASE_URL = os.getenv(
    "FIREBASE_URL",
    "https://shopmduy-default-rtdb.asia-southeast1.firebasedatabase.app"
).rstrip("/")

FIREBASE_AUTH = os.getenv("FIREBASE_AUTH", "")

# Điền Telegram ID admin trong Environment của Render
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

OTP_EXPIRE = 300
REQUEST_TIMEOUT = 20

if not BOT_TOKEN or not LINK4M_TOKEN:
    raise RuntimeError("Thiếu BOT_TOKEN hoặc LINK4M_TOKEN")

if ADMIN_ID <= 0:
    raise RuntimeError("Bạn chưa cấu hình ADMIN_ID trên Render")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

# ==================================================
# DỮ LIỆU
# ==================================================

PRODUCTS = {}
USER_SESSIONS = {}
OTP_CODES = {}

data_lock = threading.RLock()


# ==================================================
# FIREBASE
# ==================================================

def firebase_request(method, path, data=None):
    url = f"{FIREBASE_URL}/{path}.json"

    params = {}
    if FIREBASE_AUTH:
        params["auth"] = FIREBASE_AUTH

    response = requests.request(
        method=method,
        url=url,
        params=params,
        json=data,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    if response.text:
        return response.json()

    return None


def firebase_save(path, data):
    return firebase_request("PUT", path, data)


def firebase_delete(path):
    return firebase_request("DELETE", path)


def firebase_load(path):
    return firebase_request("GET", path)


def load_database():
    """Tải toàn bộ dữ liệu đã lưu từ Firebase."""

    global PRODUCTS, USER_SESSIONS, OTP_CODES

    with data_lock:
        PRODUCTS = firebase_load("products") or {}
        USER_SESSIONS = firebase_load("sessions") or {}
        OTP_CODES = firebase_load("otp_codes") or {}

    logging.info("Đã tải dữ liệu từ Firebase")
    logging.info("Số sản phẩm: %s", len(PRODUCTS))
    logging.info("Số phiên: %s", len(USER_SESSIONS))
    logging.info("Số OTP: %s", len(OTP_CODES))


def save_product(product_id):
    firebase_save(
        f"products/{product_id}",
        PRODUCTS[product_id]
    )


# ==================================================
# HÀM HỖ TRỢ
# ==================================================

def is_admin(user_id):
    return int(user_id) == ADMIN_ID


def make_id():
    return secrets.token_urlsafe(6)


def make_callback_token():
    return secrets.token_urlsafe(24)


def get_product_by_name(name):
    for product_id, product in PRODUCTS.items():
        if product.get("name") == name:
            return product_id, product

    return None, None


def create_short_link(chat_id):
    """Tạo link Link4M cho phiên hiện tại."""

    chat_key = str(chat_id)

    with data_lock:
        session = USER_SESSIONS.get(chat_key)

        if not session:
            return None

        token = make_callback_token()
        session["expected_token"] = token

        firebase_save(f"sessions/{chat_key}", session)

    target_url = (
        f"{RENDER_URL}/callback/{chat_id}/{token}"
    )

    api_url = "https://link4m.co/api-shorten/v2"

    response = requests.get(
        api_url,
        params={
            "api": LINK4M_TOKEN,
            "url": target_url
        },
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()
    result = response.json()

    if result.get("status") != "success":
        raise RuntimeError(
            result.get("message", "Không tạo được link")
        )

    short_url = result.get("shortenedUrl")

    if not short_url:
        raise RuntimeError("Link4M không trả về shortenedUrl")

    return short_url


def send_task_link(chat_id):
    try:
        short_url = create_short_link(chat_id)

        if not short_url:
            return False

        chat_key = str(chat_id)
        session = USER_SESSIONS.get(chat_key)

        if not session:
            return False

        product = PRODUCTS.get(session["product_id"])

        if not product:
            return False

        done = int(session.get("links_done", 0))
        required = int(product["links_required"])

        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton(
                f"👉 VƯỢT LINK {done + 1}/{required}",
                url=short_url
            )
        )

        bot.send_message(
            chat_id,
            f"Đã chọn: {product['name']}\n"
            f"Bấm nút bên dưới để tiếp tục nhiệm vụ.",
            reply_markup=markup
        )

        return True

    except Exception as error:
        logging.exception("Lỗi tạo link: %s", error)
        return False


# ==================================================
# CALLBACK LINK4M
# ==================================================

@app.route("/callback/<chat_id>/<token>", methods=["GET"])
def link4m_callback(chat_id, token):

    try:
        chat_id = int(chat_id)
        chat_key = str(chat_id)

        with data_lock:
            session = USER_SESSIONS.get(chat_key)

            if not session:
                return "Phiên không tồn tại hoặc đã hoàn thành", 404

            expected = session.get("expected_token", "")

            # Chặn callback dùng lại token cũ
            if not expected or not secrets.compare_digest(
                str(expected),
                str(token)
            ):
                return "Token không hợp lệ hoặc đã được sử dụng", 403

            product_id = session.get("product_id")
            product = PRODUCTS.get(product_id)

            if not product:
                return "Sản phẩm không tồn tại", 404

            # Vô hiệu token vừa sử dụng
            session["expected_token"] = ""

            session["links_done"] = (
                int(session.get("links_done", 0)) + 1
            )

            done = session["links_done"]
            required = int(product["links_required"])

            if done >= required:
                del USER_SESSIONS[chat_key]
                firebase_delete(f"sessions/{chat_key}")

                otp = "".join(
                    secrets.choice(string.digits)
                    for _ in range(6)
                )

                while otp in OTP_CODES:
                    otp = "".join(
                        secrets.choice(string.digits)
                        for _ in range(6)
                    )

                otp_data = {
                    "chat_id": chat_id,
                    "product_id": product_id,
                    "expires_at": int(time.time()) + OTP_EXPIRE
                }

                OTP_CODES[otp] = otp_data
                firebase_save(f"otp_codes/{otp}", otp_data)

                completed = True

            else:
                firebase_save(
                    f"sessions/{chat_key}",
                    session
                )
                completed = False

        if completed:
            bot.send_message(
                chat_id,
                "🎉 VƯỢT LINK THÀNH CÔNG!\n\n"
                f"Mã nhận tài khoản của bạn:\n"
                f"/claim {otp}\n\n"
                "Mã có hiệu lực trong 5 phút và chỉ dùng một lần."
            )

            return "Hoàn thành nhiệm vụ!", 200

        bot.send_message(
            chat_id,
            f"Đã hoàn thành {done}/{required} link."
        )

        if not send_task_link(chat_id):
            bot.send_message(
                chat_id,
                "Không tạo được link tiếp theo. "
                "Vui lòng liên hệ admin."
            )

        return "Đã ghi nhận lượt vượt link", 200

    except Exception:
        logging.exception("Lỗi callback Link4M")
        return "Lỗi máy chủ", 500


# ==================================================
# LỆNH CLAIM
# ==================================================

@bot.message_handler(commands=["claim"])
def claim_acc(message):

    chat_id = message.chat.id

    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        bot.reply_to(message, "Cú pháp: /claim 123456")
        return

    otp = parts[1].strip()

    with data_lock:
        otp_data = OTP_CODES.get(otp)

        if not otp_data:
            bot.reply_to(
                message,
                "❌ Mã OTP không hợp lệ hoặc đã được sử dụng!"
            )
            return

        if int(otp_data["chat_id"]) != chat_id:
            bot.reply_to(
                message,
                "❌ Bạn không phải người sở hữu mã này!"
            )
            return

        if int(otp_data["expires_at"]) < int(time.time()):
            del OTP_CODES[otp]
            firebase_delete(f"otp_codes/{otp}")

            bot.reply_to(
                message,
                "❌ Mã OTP đã hết hạn!"
            )
            return

        product_id = otp_data["product_id"]
        product = PRODUCTS.get(product_id)

        if not product or not product.get("stock"):
            bot.reply_to(
                message,
                "❌ Sản phẩm hiện đã hết hàng!"
            )
            return

        # Lấy tài khoản đầu tiên trong kho
        account = product["stock"].pop(0)

        # Lưu kho mới trước khi gửi tài khoản
        try:
            save_product(product_id)

            del OTP_CODES[otp]
            firebase_delete(f"otp_codes/{otp}")

        except Exception:
            # Khôi phục tài khoản nếu Firebase lỗi
            product["stock"].insert(0, account)

            bot.reply_to(
                message,
                "Máy chủ đang gặp lỗi lưu dữ liệu. "
                "Vui lòng thử lại sau."
            )
            return

    username = html.escape(str(account.get("user", "")))
    password = html.escape(str(account.get("pass", "")))

    bot.send_message(
        chat_id,
        "🎁 <b>TÀI KHOẢN CỦA BẠN</b>\n\n"
        f"<code>{username} | {password}</code>\n\n"
        "Hãy lưu lại thông tin tài khoản.",
        parse_mode="HTML"
    )


# ==================================================
# START
# ==================================================

@bot.message_handler(commands=["start"])
def send_welcome(message):

    chat_id = message.chat.id

    if is_admin(chat_id):
        bot.send_message(
            chat_id,
            "👑 Chào Admin!\nDùng /admin để xem quyền."
        )
        return

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        KeyboardButton("🛒 CHỌN SẢN PHẨM")
    )

    bot.send_message(
        chat_id,
        "Chào mừng!\nBấm nút bên dưới để chọn sản phẩm.",
        reply_markup=markup
    )


# ==================================================
# ADMIN
# ==================================================

@bot.message_handler(commands=["admin"])
def admin_panel(message):

    if not is_admin(message.chat.id):
        return

    text = (
        "👑 QUYỀN ADMIN\n\n"
        "/add_prod TênSP | SốLink\n"
        "/add_acc TênSP | user | pass\n"
        "/kho\n"
    )

    bot.send_message(message.chat.id, text)


@bot.message_handler(commands=["add_prod"])
def add_prod(message):

    if not is_admin(message.chat.id):
        return

    try:
        content = message.text.split(maxsplit=1)[1]
        name, links = content.split("|", 1)

        name = name.strip()
        links = int(links.strip())

        if not name or links < 1:
            raise ValueError("Thông tin không hợp lệ")

        with data_lock:
            product_id, product = get_product_by_name(name)

            if product:
                product["links_required"] = links
            else:
                product_id = make_id()

                PRODUCTS[product_id] = {
                    "name": name,
                    "links_required": links,
                    "stock": []
                }

            save_product(product_id)

        bot.reply_to(
            message,
            f"✅ Đã lưu sản phẩm: {name}\n"
            f"Số link yêu cầu: {links}"
        )

    except Exception as error:
        logging.exception("Lỗi add_prod")

        bot.reply_to(
            message,
            "Cú pháp:\n/add_prod VIP | 2"
        )


@bot.message_handler(commands=["add_acc"])
def add_acc(message):

    if not is_admin(message.chat.id):
        return

    try:
        content = message.text.split(maxsplit=1)[1]
        product_name, username, password = content.split("|", 2)

        product_name = product_name.strip()

        with data_lock:
            product_id, product = get_product_by_name(
                product_name
            )

            if not product:
                bot.reply_to(
                    message,
                    "❌ Sản phẩm không tồn tại!"
                )
                return

            product["stock"].append({
                "user": username.strip(),
                "pass": password.strip()
            })

            save_product(product_id)

        bot.reply_to(
            message,
            f"✅ Đã thêm tài khoản vào {product_name}"
        )

    except Exception:
        bot.reply_to(
            message,
            "Cú pháp:\n/add_acc VIP | user1 | pass1"
        )


@bot.message_handler(commands=["kho"])
def kho(message):

    if not is_admin(message.chat.id):
        return

    with data_lock:
        if not PRODUCTS:
            bot.send_message(
                message.chat.id,
                "Kho hiện chưa có sản phẩm."
            )
            return

        lines = ["📦 TỒN KHO"]

        for product in PRODUCTS.values():
            lines.append(
                f"- {product['name']}: "
                f"{len(product.get('stock', []))} acc "
                f"(Cần {product['links_required']} link)"
            )

    bot.send_message(
        message.chat.id,
        "\n".join(lines)
    )


# ==================================================
# CHỌN SẢN PHẨM
# ==================================================

@bot.message_handler(
    func=lambda message: message.text == "🛒 CHỌN SẢN PHẨM"
)
def list_products(message):

    with data_lock:
        products = list(PRODUCTS.items())

    if not products:
        bot.send_message(
            message.chat.id,
            "Hiện chưa có sản phẩm."
        )
        return

    markup = InlineKeyboardMarkup()

    for product_id, product in products:
        markup.add(
            InlineKeyboardButton(
                f"🎁 {product['name']}",
                callback_data=f"buy_{product_id}"
            )
        )

    bot.send_message(
        message.chat.id,
        "Chọn sản phẩm:",
        reply_markup=markup
    )


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("buy_")
)
def buy_product(call):

    product_id = call.data[4:]
    chat_id = call.message.chat.id
    chat_key = str(chat_id)

    with data_lock:
        if chat_key in USER_SESSIONS:
            bot.answer_callback_query(
                call.id,
                "Bạn đang có nhiệm vụ chưa hoàn thành!",
                show_alert=True
            )
            return

        product = PRODUCTS.get(product_id)

        if not product or not product.get("stock"):
            bot.answer_callback_query(
                call.id,
                "Sản phẩm đã hết hàng!",
                show_alert=True
            )
            return

        session = {
            "product_id": product_id,
            "links_done": 0,
            "expected_token": ""
        }

        USER_SESSIONS[chat_key] = session

        try:
            firebase_save(
                f"sessions/{chat_key}",
                session
            )

        except Exception:
            del USER_SESSIONS[chat_key]

            bot.answer_callback_query(
                call.id,
                "Không lưu được phiên. Hãy thử lại sau.",
                show_alert=True
            )
            return

    bot.answer_callback_query(call.id)

    if not send_task_link(chat_id):
        with data_lock:
            USER_SESSIONS.pop(chat_key, None)
            firebase_delete(f"sessions/{chat_key}")

        bot.send_message(
            chat_id,
            "❌ Không tạo được link. Vui lòng thử lại sau."
        )


# ==================================================
# FLASK + TELEGRAM
# ==================================================

@app.route("/", methods=["GET"])
def home():
    return "MDUYK BOT SERVER RUNNING", 200


def run_bot():
    logging.info("Telegram bot đang chạy...")
    bot.infinity_polling(
        skip_pending=True,
        timeout=30,
        long_polling_timeout=30
    )


if __name__ == "__main__":

    # Tải dữ liệu trước khi chạy bot
    load_database()

    thread = threading.Thread(
        target=run_bot,
        daemon=True
    )
    thread.start()

    port = int(os.getenv("PORT", "3000"))

    app.run(
        host="0.0.0.0",
        port=port
    )
