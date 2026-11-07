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

def get_products():
    try:
        res = requests.get(FIREBASE_URL + "products.json")
        return res.json() if res.json() else {}
    except: return {}

def save_product(prod_name, links_req):
    requests.put(FIREBASE_URL + f"products/{prod_name}/links_required.json", json=links_req)

def add_acc_to_db(prod_name, user, pwd):
    requests.post(FIREBASE_URL + f"products/{prod_name}/stock.json", json={"user": user, "pass": pwd})

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def receive_update():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return '', 403

# --- HÀM TẠO LINK (ẨN MÃ TOKEN) ---
def generate_link4m(chat_id, prod_name, links_done, req_links):
    # Tạo mã Token duy nhất, KHÔNG hiển thị cho khách
    unique_token = f"MDUYK-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"
    
    # Lưu Token vào Firebase
    requests.put(FIREBASE_URL + f"sessions/{chat_id}/active_token.json", json=unique_token)
    
    # Gắn Token vào URL
    target_url = f"{RENDER_URL}/callback/{chat_id}/{unique_token}"
    api_url = f"https://link4m.co/api-shorten/v2?api={LINK4M_TOKEN}&url={target_url}"
    
    try:
        res = requests.get(api_url, timeout=10).json()
        if res.get('status') == 'success':
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton(f"👉 VƯỢT LINK {links_done + 1}/{req_links}", url=res.get('shortenedUrl')))
            # ĐÃ XÓA PHẦN HIỂN THỊ MÃ TOKEN
            bot.send_message(chat_id, f"Vui lòng vượt link {links_done + 1}/{req_links} bên dưới.", reply_markup=markup)
    except:
        bot.send_message(chat_id, "❌ Lỗi tạo link từ Link4M!")

# --- WEBHOOK NHẬN KẾT QUẢ ---
@app.route('/callback/<chat_id>/<token_from_url>', methods=['GET'])
def link4m_callback(chat_id, token_from_url):
    try:
        chat_id = int(chat_id)
        res = requests.get(FIREBASE_URL + f"sessions/{chat_id}.json")
        session = res.json()
        
        if session:
            saved_token = session.get("active_token")
            
            # Nếu mã không khớp (ví dụ F5), trả về HTML báo lỗi
            if saved_token != token_from_url:
                html = """
                <html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
                <body style="background:#0b090a;color:#f6eef0;text-align:center;padding-top:50px;font-family:sans-serif;">
                <h2 style="color:#a91f2b;">LỖI XÁC THỰC</h2>
                <p>Link này đã được sử dụng hoặc không hợp lệ.</p>
                <p>Vui lòng quay lại Telegram để lấy link vượt tiếp theo!</p>
                </body></html>
                """
                return html, 403
            
            # Xóa token ngay lập tức
            requests.delete(FIREBASE_URL + f"sessions/{chat_id}/active_token.json")
            
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
                
                html_ok = """
                <html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
                <body style="background:#0b090a;color:#61c995;text-align:center;padding-top:50px;font-family:sans-serif;">
                <h2>THÀNH CÔNG!</h2>
                <p>Đã vượt đủ số link.</p>
                <p>Vui lòng quay lại Telegram để nhận mã OTP.</p>
                </body></html>
                """
                return html_ok, 200
            else:
                requests.put(FIREBASE_URL + f"sessions/{chat_id}/links_done.json", json=links_done)
                generate_link4m(chat_id, prod_name, links_done, req_links)
                
                html_next = f"""
                <html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
                <body style="background:#0b090a;color:#f6eef0;text-align:center;padding-top:50px;font-family:sans-serif;">
                <h2 style="color:#61c995;">ĐÃ XÁC NHẬN LINK {links_done}/{req_links}</h2>
                <p>Vui lòng quay lại Telegram để bấm vượt link tiếp theo.</p>
                </body></html>
                """
                return html_next, 200
                
        return "Session not found", 404
    except Exception as e:
        return "Error", 500

# --- CÁC LỆNH CƠ BẢN ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    global ADMIN_ID
    chat_id = message.chat.id
    try:
        res = requests.get(FIREBASE_URL + "admin_id.json")
        saved_admin = res.json()
    except: saved_admin = None

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
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton("🛒 CHỌN SẢN PHẨM"))
        bot.send_message(chat_id, "Chào mừng bạn! Hãy chọn sản phẩm.", reply_markup=markup)

@bot.message_handler(commands=['force_admin'])
def force_admin(message):
    chat_id = message.chat.id
    requests.put(FIREBASE_URL + "admin_id.json", json=chat_id)
    global ADMIN_ID
    ADMIN_ID = chat_id
    bot.reply_to(message, "👑 Đã cấp quyền Admin cho bạn!")

@bot.message_handler(commands=['add_prod'])
def add_prod(message):
    global ADMIN_ID
    if message.chat.id != ADMIN_ID: return
    try:
        parts = message.text.replace('/add_prod', '').strip().split('|')
        name = parts[0].strip()
        links = int(parts[1].strip())
        save_product(name, links)
        bot.reply_to(message, f"✅ Đã thêm SP: {name} (Cần {links} link)")
    except Exception as e: 
        bot.reply_to(message, f"❌ Lỗi cú pháp! VD: `/add_prod VIP | 2`", parse_mode='Markdown')

@bot.message_handler(commands=['add_acc'])
def add_acc(message):
    global ADMIN_ID
    if message.chat.id != ADMIN_ID: return
    try:
        parts = message.text.replace('/add_acc', '').strip().split('|')
        add_acc_to_db(parts[0].strip(), parts[1].strip(), parts[2].strip())
        bot.reply_to(message, f"✅ Đã thêm acc vào {parts[0].strip()}")
    except Exception as e: 
        bot.reply_to(message, f"❌ Lỗi cú pháp! VD: `/add_acc VIP | user | pass`", parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "🛒 CHỌN SẢN PHẨM")
def list_products(message):
    products = get_products()
    if not products: 
        bot.send_message(message.chat.id, "Chưa có sản phẩm nào!")
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
        prod_name = urllib.parse.unquote(call.data.split('_', 1)[1])
        chat_id = call.message.chat.id
        products = get_products()
        
        if prod_name not in products:
             bot.send_message(chat_id, "❌ Sản phẩm không tồn tại!")
             return

        req_links = products[prod_name]["links_required"]
        requests.put(FIREBASE_URL + f"sessions/{chat_id}.json", json={"product": prod_name, "links_done": 0, "links_required": req_links})
        generate_link4m(chat_id, prod_name, 0, req_links)
            
    except Exception as e:
        print("Lỗi nút bấm:", e)

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
            bot.reply_to(message, "❌ Kho đã hết tài khoản! Vui lòng liên hệ @mduyk để hỗ trợ.")
            return
            
        acc_key = list(stock.keys())[0]
        acc_data = stock[acc_key]
        
        requests.delete(FIREBASE_URL + f"products/{prod_name}/stock/{acc_key}.json")
        requests.delete(FIREBASE_URL + f"otps/{otp}.json")
        
        bot.reply_to(message, f"🎁 **TÀI KHOẢN CỦA BẠN:**\n\n`{acc_data['user']} | {acc_data['pass']}`\n\n*(Hãy copy ngay)*", parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"Lỗi: {e}")

def keep_alive():
    while True:
        time.sleep(600) 
        try: requests.get(RENDER_URL)
        except: pass

if __name__ == '__main__':
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"{RENDER_URL}/{BOT_TOKEN}")
    threading.Thread(target=keep_alive, daemon=True).start()
    app.run(host='0.0.0.0', port=3000)
