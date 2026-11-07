import os
import time
import html
import secrets
import string
import logging
import threading

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
# CONFIG
# ==================================================

BOT_TOKEN = os.getenv("8314558446:AAFGz92fVeLdomzfN0EeNZk-HFtDSC8hHEg", "")
LINK4M_TOKEN = os.getenv("699ac288bb556c3eae114a58", "")

RENDER_URL = os.getenv(
    "RENDER_URL",
    "https://voice-mleh.onrender.com"
).rstrip("/")

FIREBASE_URL = os.getenv(
    "FIREBASE_URL",
    "https://shopmduy-default-rtdb.asia-southeast1.firebasedatabase.app"
).rstrip("/")

FIREBASE_AUTH = os.getenv("FIREBASE_AUTH", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

OTP_EXPIRE = 300
REQUEST_TIMEOUT = 20

if not BOT_TOKEN:
    raise RuntimeError("Thiếu BOT_TOKEN")

if not LINK4M_TOKEN:
    raise RuntimeError("Thiếu LINK4M_TOKEN")

if ADMIN_ID <= 0:
    raise RuntimeError("Thiếu ADMIN_ID")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

# ==================================================
# DATA
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
        method,
        url,
        params=params,
        json=data,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    if response.text:
        return response.json()

    return None


def firebase_get(path):
    return firebase_request("GET", path)


def firebase_put(path, data):
    return firebase_request("PUT", path, data)


def firebase_delete(path):
    return firebase_request("DELETE", path)


def load_database():
    global PRODUCTS, USER_SESSIONS, OTP_CODES

    logging.info("Đang tải dữ liệu Firebase...")

    products = firebase_get("products") or {}
    sessions = firebase_get("sessions") or {}
    otps = firebase_get("otp_codes") or {}

    with data_lock:
        PRODUCTS = products
        USER_SESSIONS = sessions
        OTP_CODES = otps

    logging.info("Đã tải dữ liệu Firebase")
    logging.info("Sản phẩm: %s", len(PRODUCTS))
    logging.info("Phiên: %s", len(USER_SESSIONS))
    logging.info("OTP: %s", len(OTP_CODES))


def save_product(product_id):
    firebase_put(
        f"products/{product_id}",
        PRODUCTS[product_id]
    )


# ==================================================
# HELPERS
# ==================================================

def is_admin(user_id):
    return int(user_id) == ADMIN_ID


def make_id():
    return secrets.token_urlsafe(8)


def make_token():
    return secrets.token_urlsafe(24)


def find_product(name):
    for product_id, product in PRODUCTS.items():
        if product.get("name") == name:
            return product_id, product

    return None, None


# ==================================================
# LINK4M
# ==================================================

def create_short_link(chat_id):
    chat_key = str(chat_id)

    with data_lock:
        session = USER_SESSIONS.get(chat_key)

        if not session:
            return None

        token = make_token()
        session["expected_token"] = token

        firebase_put(
            f"sessions/{chat_key}",
            session
        )

    target_url = (
        f"{RENDER_URL}/callback/{chat_id}/{token}"
    )

    response = requests.get(
        "https://link4m.co/api-shorten/v2",
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
            result.get("message", "Link4M tạo link thất bại")
        )

    short_url = result.get("shortenedUrl")

    if not short_url:
        raise RuntimeError("Không nhận được shortenedUrl")

    return short_url


def send_task_link(chat_id):
    try:
        short_url = create_short_link(chat_id)

        if not short_url:
            return False

        chat_key = str(chat_id)

        with data_lock:
            session = USER_SESSIONS.get(chat_key)

            if not session:
                return False

            product = PRODUCTS.get(
                session["product_id"]
            )

            if not product:
                return False

            done = int(session.get("links_done", 0))
            required = int(product["links_required"])
            product_name = product["name"]

        markup = InlineKeyboardMarkup()

        markup.add(
            InlineKeyboardButton(
                f"👉 VƯỢT LINK {done + 1}/{required}",
                url=short_url
            )
        )

        bot.send_message(
            chat_id,
            f"Đã chọn: {product_name}\n"
            "Bấm nút bên dưới để tiếp tục nhiệm vụ.",
            reply_markup=markup
        )

        return True

    except Exception:
        logging.exception("Lỗi tạo link")
        return False


# ==================================================
# CALLBACK
# ==================================================

@app.route("/callback/<chat_id>/<token>", methods=["GET"])
def link4m_callback(chat_id, token):

    try:
        chat_id = int(chat_id)
        chat_key = str(chat_id)

        with data_lock:
            session = USER_SESSIONS.get(chat_key)

            if not session:
                return "Phiên không tồn tại hoặc đã kết thúc", 404

            expected = session.get("expected_token", "")

            if not expected or not secrets.compare_digest(
                str(expected),
                str(token)
            ):
                return "Token không hợp lệ hoặc đã sử dụng", 403

            product_id = session.get("product_id")
            product = PRODUCTS.get(product_id)

            if not product:
                return "Không tìm thấy sản phẩm", 404

            # Chặn sử dụng lại callback token
            session["expected_token"] = ""

            session["links_done"] = (
                int(session.get("links_done", 0)) + 1
            )

            done = session["links_done"]
            required = int(product["links_required"])

            if done >= required:
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

                firebase_put(
                    f"otp_codes/{otp}",
                    otp_data
                )

                firebase_delete(
                    f"sessions/{chat_key}"
                )

                OTP_CODES[otp] = otp_data
                del USER_SESSIONS[chat_key]

                completed = True

            else:
                firebase_put(
                    f"sessions/{chat_key}",
                    session
                )

                completed = False

        if completed:
            bot.send_message(
                chat_id,
                "🎉 VƯỢT LINK THÀNH CÔNG!\n\n"
                f"Mã nhận tài khoản:\n/claim {otp}\n\n"
                "Mã có hiệu lực trong 5 phút."
            )

            return "Hoàn thành!", 200

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

        return "Đã ghi nhận", 200

    except Exception:
        logging.exception("Lỗi callback")
        return "Server error", 500


# ==================================================
# CLAIM
# ==================================================

@bot.message_handler(commands=["claim"])
def claim_acc(message):

    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        bot.reply_to(message, "Cú pháp: /claim 123456")
        return

    otp = parts[1].strip()
    chat_id = message.chat.id

    with data_lock:
        otp_data = OTP_CODES.get(otp)

        if not otp_data:
            bot.reply_to(
                message,
                "❌ OTP không hợp lệ hoặc đã sử dụng!"
            )
            return

        if int(otp_data["chat_id"]) != chat_id:
            bot.reply_to(
                message,
                "❌ Bạn không sở hữu mã OTP này!"
            )
            return

        if int(otp_data["expires_at"]) < int(time.time()):
            del OTP_CODES[otp]
            firebase_delete(f"otp_codes/{otp}")

            bot.reply_to(message, "❌ OTP đã hết hạn!")
            return

        product_id = otp_data["product_id"]
        product = PRODUCTS.get(product_id)

        if not product or not product.get("stock"):
            bot.reply_to(message, "❌ Sản phẩm đã hết hàng!")
            return

        account = product["stock"].pop(0)

        try:
            # Lưu kho mới trước khi gửi tài khoản
            save_product(product_id)

            firebase_delete(f"otp_codes/{otp}")
            del OTP_CODES[otp]

        except Exception:
            product["stock"].insert(0, account)

            logging.exception("Không lưu được kho")

            bot.reply_to(
                message,
                "Lỗi lưu dữ liệu. Vui lòng thử lại."
            )
            return

    username = html.escape(str(account.get("user", "")))
    password = html.escape(str(account.get("pass", "")))

    bot.send_message(
        chat_id,
        "<b>🎁 TÀI KHOẢN CỦA BẠN</b>\n\n"
        f"<code>{username} | {password}</code>",
        parse_mode="HTML"
    )


# ==================================================
# START
# ==================================================

@bot.message_handler(commands=["start"])
def send_welcome(message):

    if is_admin(message.chat.id):
        bot.send_message(
            message.chat.id,
            "👑 Chào Admin!\nDùng /admin để xem quyền."
        )
        return

    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.add(
        KeyboardButton("🛒 CHỌN SẢN PHẨM")
    )

    bot.send_message(
        message.chat.id,
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

    bot.send_message(
        message.chat.id,
        "👑 QUYỀN ADMIN\n\n"
        "/add_prod TênSP | SốLink\n"
        "/add_acc TênSP | user | pass\n"
        "/kho"
    )


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
            raise ValueError("Dữ liệu không hợp lệ")

        with data_lock:
            product_id, product = find_product(name)

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
            f"✅ Đã lưu sản phẩm {name}\n"
            f"Số link: {links}"
        )

    except Exception:
        logging.exception("Lỗi add_prod")

        bot.reply_to(
            message,
            "Cú pháp: /add_prod VIP | 2"
        )


@bot.message_handler(commands=["add_acc"])
def add_acc(message):

    if not is_admin(message.chat.id):
        return

    try:
        content = message.text.split(maxsplit=1)[1]

        name, username, password = content.split("|", 2)

        name = name.strip()

        with data_lock:
            product_id, product = find_product(name)

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
            f"✅ Đã thêm acc vào {name}"
        )

    except Exception:
        logging.exception("Lỗi add_acc")

        bot.reply_to(
            message,
            "Cú pháp: /add_acc VIP | user1 | pass1"
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
            firebase_put(
                f"sessions/{chat_key}",
                session
            )

        except Exception:
            del USER_SESSIONS[chat_key]

            logging.exception("Không lưu được phiên")

            bot.answer_callback_query(
                call.id,
                "Lỗi lưu phiên. Thử lại sau.",
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
            "❌ Không tạo được link. Vui lòng thử lại."
        )


# ==================================================
# WEB SERVER
# ==================================================

@app.route("/", methods=["GET"])
def home():
    return "MDUYK BOT SERVER RUNNING", 200


# ==================================================
# RUN BOT
# ==================================================

def run_bot():

    try:
        logging.info("Đang xóa Telegram webhook cũ...")

        # SỬA LỖI 409: XÓA WEBHOOK TRƯỚC KHI POLLING
        bot.remove_webhook()

        time.sleep(2)

        logging.info("Webhook đã xóa")
        logging.info("Telegram bot bắt đầu Polling")

        bot.infinity_polling(
            skip_pending=True,
            timeout=30,
            long_polling_timeout=30
        )

    except Exception:
        logging.exception("Bot gặp lỗi khi chạy")


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
