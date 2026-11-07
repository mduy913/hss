import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import requests
import random
import string
import threading
import time
import urllib.parse
from flask import Flask, request

# ================= CẤU HÌNH =================
BOT_TOKEN = "8314558446:AAFGz92fVeLdomzfN0EeNZk-HFtDSC8hHEg"
LINK4M_TOKEN = "699ac288bb556c3eae114a58"
RENDER_URL = "https://hss-hsha.onrender.com" 
FIREBASE_URL = "https://shopmduy-default-rtdb.asia-southeast1.firebasedatabase.app/"
# ============================================

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

ADMIN_ID = None 

# --- HÀM LẤY DỮ LIỆU TỪ FIREBASE ---
def get_products():
    try:
        res = requests.get(FIREBASE_URL + "products.json")
        return res.json() if res.json() else {}
    except: return {}

def save_product(prod_name, links_req):
    requests.put(FIREBASE_URL + f"products/{prod_name}/links_required.json", json=links_req)

def add_acc_to_db(prod_name, user, pwd):
    requests.post(FIREBASE_URL + f"products/{prod_name}/stock.json", json={"user": user, "pass": pwd})

# --- WEBHOOK CỦA TELEGRAM ---
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def receive_update():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return '', 403

# --- CÁC LỆNH CƠ BẢN (ĐÃ SỬA LỖI ADMIN) ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    global ADMIN_ID
    chat_id = message.chat.id
    
    try:
        res = requests.get(FIREBASE_URL + "admin_id.json")
        saved_admin = res.json()
    except:
        saved_admin = None

    # Nếu chưa có Admin, hoặc có Admin cũ nhưng bạn muốn lấy lại quyền
    if saved_admin is None:
        requests.put(FIREBASE_URL + "admin_id.json", json=chat_id)
        ADMIN_ID = chat_id
        bot.send_message(chat_id, "👑 Bạn là ADMIN đầu tiên!\nHãy dùng /add_prod để tạo sản phẩm.")
        return
    
    ADMIN_ID = saved_admin
    if chat_id == ADMIN_ID:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton("🛒 CHỌN SẢN PHẨM"))
        bot.send_message(chat_id, "Chào Admin! Đã sẵn sàng.", reply_markup=markup)
    else:
        # Nếu bạn không phải admin cũ, nhưng muốn test
        bot.send_message(chat_id, f"Chào bạn! Bạn đang đăng nhập với ID: {chat_id}.\nĐể lấy quyền Admin, hãy gõ lệnh /force_admin")

@bot.message_handler(commands=['force_admin'])
def force_admin(message):
    chat_id = message.chat.id
    # Xóa admin cũ, gán admin mới
    requests.put(FIREBASE_URL + "admin_id.json", json=chat_id)
    global ADMIN_ID
    ADMIN_ID = chat_id
    bot.reply_to(message, "👑 Đã cấp quyền Admin cho bạn!")

@bot.message_handler(commands=['add_prod'])
def add_prod(message):
    global ADMIN_ID
    if ADMIN_ID is None:
        bot.reply_to(message, "Lỗi: Bot chưa nhận diện được Admin. Hãy gõ /start trước!")
        return
    if message.chat.id != ADMIN_ID: 
        bot.reply_to(message, "Bạn không phải Admin!")
        return
    
    try:
        parts = message.text.replace('/add_prod', '').strip().split('|')
        if len(parts) < 2: raise Exception("Thiếu thông tin")
        name = parts[0].strip()
        links = int(parts[1].strip())
        save_product(name, links)
        bot.reply_to(message, f"✅ Đã thêm SP: {name} (Cần {links} link)")
    except Exception as e: 
        bot.reply_to(message, f"❌ Lỗi: `/add_prod VIP | 2`\nChi tiết: {e}", parse_mode='Markdown')

@bot.message_handler(commands=['add_acc'])
def add_acc(message):
    global ADMIN_ID
    if ADMIN_ID is None:
        bot.reply_to(message, "Lỗi: Bot chưa nhận diện được Admin. Hãy gõ /start trước!")
        return
    if message.chat.id != ADMIN_ID: 
        bot.reply_to(message, "Bạn không phải Admin!")
        return

    try:
        parts = message.text.replace('/add_acc', '').strip().split('|')
        if len(parts) < 3: raise Exception("Thiếu thông tin")
        p, u, pw = parts[0].strip(), parts[1].strip(), parts[2].strip()
        add_acc_to_db(p, u, pw)
        bot.reply_to(message, f"✅ Đã thêm acc vào {p}")
    except Exception as e: 
        bot.reply_to(message, f"❌ Lỗi: `/add_acc VIP | user | pass`\nChi tiết: {e}", parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "🛒 CHỌN SẢN PHẨM")
def list_products(message):
    products = get_products()
    if not products: 
        bot.send_message(message.chat.id, "Hiện tại chưa có sản phẩm nào! Hãy dùng /add_prod để tạo.")
        return
        
    markup = InlineKeyboardMarkup()
    for name in products:
        safe_name = urllib.parse.quote(name)
        markup.add(InlineKeyboardButton(f"🎁 {name}", callback_data=f"buy_{safe_name}"))
    bot.send_message(message.chat.id, "Chọn sản phẩm:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def buy_product(call):
    try:
        bot.answer_callback_query(call.id)
        encoded_name = call.data.split('_', 1)[1]
        prod_name = urllib.parse.unquote(encoded_name)
        chat_id = call.message.chat.id
        products = get_products()
        
        if prod_name not in products:
             bot.send_message(chat_id, "❌ Sản phẩm không tồn tại trên Firebase!")
             return

        token = f"MDUYK-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"
        req_links = products[prod_name]["links_required"]
        requests.put(FIREBASE_URL + f"sessions/{chat_id}.json", json={"product": prod_name, "links_done": 0, "links_required": req_links})

        target_url = f"{RENDER_URL}/callback/{chat_id}/{token}"
        api_url = f"https://link4m.co/api-shorten/v2?api={LINK4M_TOKEN}&url={target_url}"
        
        # Gửi tin nhắn chờ
        msg_wait = bot.send_message(chat_id, "⏳ Đang tạo link, vui lòng đợi...")
        
        res = requests.get(api_url, timeout=10).json()
        if res.get('status') == 'success':
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton(f"👉 VƯỢT LINK 1/{req_links}", url=res.get('shortenedUrl')))
            bot.delete_message(chat_id, msg_wait.message_id)
            bot.send_message(chat_id, f"Đã chọn: {prod_name}\nBấm nút dưới để làm nhiệm vụ.", reply_markup=markup)
        else:
            bot.edit_message_text("❌ Link4M từ chối tạo link! (Token sai hoặc bị chặn)", chat_id, msg_wait.message_id)
            requests.delete(FIREBASE_URL + f"sessions/{chat_id}.json")
            
    except Exception as e:
        print("Lỗi nút bấm:", e)

# --- WEBHOOK CỦA LINK4M ---
@app.route('/callback/<chat_id>/<token>', methods=['GET'])
def link4m_callback(chat_id, token):
    try:
        chat_id = int(chat_id)
        res = requests.get(FIREBASE_URL + f"sessions/{chat_id}.json")
        session = res.json()
        
        if session:
            links_done = session.get("links_done", 0) + 1
            req_links = session.get("links_required", 1)
            prod_name = session.get("product")
            
            if links_done >= req_links:
                otp = ''.join(random.choices(string.digits, k=6))
                requests.put(FIREBASE_URL + f"otps/{otp}.json", json={"chat_id": chat_id, "product": prod_name})
                requests.delete(FIREBASE_URL + f"sessions/{chat_id}.json")
                
                msg = (f"🎉 **VƯỢT LINK THÀNH CÔNG!**\n\n"
                       f"Để nhận tài khoản, hãy gõ lệnh:\n"
                       f"`/claim {otp}`\n\n"
                       f"*(Mã này sẽ hết hạn sau 5 phút)*")
                bot.send_message(chat_id, msg, parse_mode='Markdown')
            else:
                requests.put(FIREBASE_URL + f"sessions/{chat_id}/links_done.json", json=links_done)
                target_url = f"{RENDER_URL}/callback/{chat_id}/{token}"
                api_url = f"https://link4m.co/api-shorten/v2?api={LINK4M_TOKEN}&url={target_url}"
                res_link = requests.get(api_url).json()
                if res_link.get('status') == 'success':
                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton(f"👉 VƯỢT LINK {links_done + 1}/{req_links}", url=res_link.get('shortenedUrl')))
                    bot.send_message(chat_id, f"Vui lòng vượt thêm {req_links - links_done} link nữa.", reply_markup=markup)
        return "OK", 200
    except Exception as e:
        return "Error", 500

# --- LỆNH CLAIM ---
@bot.message_handler(commands=['claim'])
def claim_acc(message):
    chat_id = message.chat.id
    try:
        otp = message.text.replace('/claim', '').strip()
        res = requests.get(FIREBASE_URL + f"otps/{otp}.json")
        session = res.json()
        
        if not session:
            bot.reply_to(message, "❌ Mã OTP không hợp lệ hoặc đã hết hạn!")
            return
            
        if session["chat_id"] != chat_id:
            bot.reply_to(message, "❌ Không phải mã của bạn!")
            return
            
        prod_name = session["product"]
        res_acc = requests.get(FIREBASE_URL + f"products/{prod_name}/stock.json")
        stock = res_acc.json()
        
        if not stock:
            requests.delete(FIREBASE_URL + f"otps/{otp}.json")
            bot.reply_to(message, "❌ Kho đã hết tài khoản! Vui lòng chờ Admin up thêm.")
            return
            
        acc_key = list(stock.keys())[0]
        acc_data = stock[acc_key]
        
        requests.delete(FIREBASE_URL + f"products/{prod_name}/stock/{acc_key}.json")
        requests.delete(FIREBASE_URL + f"otps/{otp}.json")
        
        bot.reply_to(message, f"🎁 **TÀI KHOẢN CỦA BẠN:**\n\n`{acc_data['user']} | {acc_data['pass']}`\n\n*(Hãy copy ngay)*", parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"Lỗi: {e}")

# --- HÀM CHỐNG NGỦ ---
def keep_alive():
    while True:
        time.sleep(600) 
        try: requests.get(RENDER_URL)
        except: pass

# --- KHỞI ĐỘNG ---
if __name__ == '__main__':
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"{RENDER_URL}/{BOT_TOKEN}")
    threading.Thread(target=keep_alive, daemon=True).start()
    app.run(host='0.0.0.0', port=3000)
