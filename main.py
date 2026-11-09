import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ForceReply
import requests
import random
import string
import threading
import time
import urllib.parse
from datetime import datetime, timedelta
from flask import Flask, request

# ================= CẤU HÌNH =================
BOT_TOKEN = "8314558446:AAFGz92fVeLdomzfN0EeNZk-HFtDSC8hHEg"
LINK4M_TOKEN = "699ac288bb556c3eae114a58"
LAYMA_TOKEN = "b7d4d3eb19b808e8b529f9c13e053c75"
RENDER_URL = "https://hss-hsha.onrender.com" 
FIREBASE_URL = "https://shopmduy-default-rtdb.asia-southeast1.firebasedatabase.app/"
# ============================================

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

ADMIN_ID = None 

def get_today():
    return datetime.now().strftime("%Y-%m-%d")

def get_products():
    try:
        res = requests.get(FIREBASE_URL + "products.json")
        return res.json() if res.json() else {}
    except: return {}

# ================= HÀM TẠO LINK (LAYMA -> LINK4M) =================
def generate_link4m(chat_id, prod_id, links_done, req_links):
    unique_token = f"MDUYK-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"
    requests.put(FIREBASE_URL + f"sessions/{chat_id}/active_token.json", json=unique_token)
    
    target_url = f"{RENDER_URL}/callback/{chat_id}/{unique_token}"
    final_short_url = None
    
    # --- 1. THỬ GỌI LAYMA TRƯỚC ---
    try:
        layma_api = f"https://api.layma.net/api/admin/shortlink/quicklink?tokenUser={LAYMA_TOKEN}&format=json&url={target_url}"
        res_layma = requests.get(layma_api, timeout=10).json()
        
        # LayMa trả về success: true và link trong "html"
        if res_layma.get("success") is True and res_layma.get("html"):
            final_short_url = res_layma.get("html")
            print("-> Đã tạo link qua LayMa")
    except Exception as e:
        print("Lỗi gọi LayMa:", e)

    # --- 2. NẾU LAYMA LỖI, GỌI LINK4M ---
    if not final_short_url:
        print("-> LayMa lỗi, chuyển sang Link4M")
        try:
            link4m_api = f"https://link4m.co/api-shorten/v2?api={LINK4M_TOKEN}&url={target_url}"
            res_link4m = requests.get(link4m_api, timeout=10).json()
            if res_link4m.get('status') == 'success':
                final_short_url = res_link4m.get('shortenedUrl')
        except Exception as e:
            print("Lỗi gọi Link4M:", e)

    # --- 3. GỬI KẾT QUẢ ---
    if final_short_url:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(f"👉 VƯỢT LINK {links_done + 1}/{req_links}", url=final_short_url))
        bot.send_message(chat_id, f"Vui lòng vượt link {links_done + 1}/{req_links} bên dưới.", reply_markup=markup)
    else:
        bot.send_message(chat_id, "❌ Hệ thống tạo link thất bại (Cả LayMa và Link4M đều lỗi). Vui lòng thử lại sau!")

# ================= HÀM TỰ ĐỘNG XOÁ LỊCH SỬ LÚC 00:00 =================
def reset_daily_history():
    while True:
        now = datetime.now()
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        seconds_until_midnight = (tomorrow - now).total_seconds()
        time.sleep(seconds_until_midnight) 
        try:
            requests.delete(FIREBASE_URL + "history.json")
            print("-> Đã reset toàn bộ lịch sử lấy acc lúc 00:00")
        except Exception as e:
            print("Lỗi reset history:", e)

# ================= WEBHOOKS =================
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def receive_update():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return '', 403

@app.route('/callback/<chat_id>/<token_from_url>', methods=['GET'])
def link4m_callback(chat_id, token_from_url):
    try:
        chat_id = int(chat_id)
        res = requests.get(FIREBASE_URL + f"sessions/{chat_id}.json")
        session = res.json()
        
        if session:
            saved_token = session.get("active_token")
            if saved_token != token_from_url:
                return "<html><body style='background:#0b090a;color:#f6eef0;text-align:center;padding-top:50px;'><h2 style='color:#a91f2b;'>LỖI XÁC THỰC</h2></body></html>", 403
            
            requests.delete(FIREBASE_URL + f"sessions/{chat_id}/active_token.json")
            links_done = session.get("links_done", 0) + 1
            req_links = session.get("links_required", 1)
            prod_id = session.get("product_id")
            
            if links_done >= req_links:
                otp = ''.join(random.choices(string.digits, k=6))
                requests.put(FIREBASE_URL + f"otps/{otp}.json", json={"chat_id": chat_id, "product_id": prod_id})
                requests.delete(FIREBASE_URL + f"sessions/{chat_id}.json")
                
                msg = (f"🎉 **VƯỢT LINK THÀNH CÔNG!**\n\n"
                       f"Để nhận tài khoản, hãy gõ lệnh:\n"
                       f"`/claim {otp}`\n\n"
                       f"*(Mã này sẽ hết hạn sau 5 phút)*")
                bot.send_message(chat_id, msg, parse_mode='Markdown')
                return "<html><body style='background:#0b090a;color:#61c995;text-align:center;padding-top:50px;'><h2>THÀNH CÔNG!</h2></body></html>", 200
            else:
                requests.put(FIREBASE_URL + f"sessions/{chat_id}/links_done.json", json=links_done)
                generate_link4m(chat_id, prod_id, links_done, req_links)
                return f"<html><body style='background:#0b090a;color:#61c995;text-align:center;padding-top:50px;'><h2>ĐÃ XÁC NHẬN {links_done}/{req_links}</h2></body></html>", 200
        return "Session not found", 404
    except Exception as e:
        return "Error", 500

# ================= GIAO DIỆN CHUNG =================
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
        bot.send_message(chat_id, "👑 Bạn là ADMIN đầu tiên!\nBấm nút bên dưới.", reply_markup=admin_main_menu())
        return
    
    ADMIN_ID = saved_admin
    if chat_id == ADMIN_ID:
        bot.send_message(chat_id, "Chào Admin! Bấm nút bên dưới để quản lý.", reply_markup=admin_main_menu())
    else:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🛒 CHỌN SẢN PHẨM", callback_data="user_products"))
        bot.send_message(chat_id, "Chào mừng bạn! Hãy chọn sản phẩm.", reply_markup=markup)

# --- MENU ADMIN ---
def admin_main_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("➕ Thêm Sản Phẩm", callback_data="admin_add_prod"),
        InlineKeyboardButton("➕ Thêm Acc", callback_data="admin_add_acc")
    )
    markup.add(
        InlineKeyboardButton("📦 Xem Kho Hàng", callback_data="admin_view_stock"),
        InlineKeyboardButton("⚙️ Chỉnh Sửa Sản Phẩm", callback_data="admin_edit_prod_menu")
    )
    markup.add(InlineKeyboardButton("🔄 Quay Lại", callback_data="admin_back"))
    return markup

def back_button():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 Quay Lại", callback_data="admin_back"))
    return markup

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def handle_admin_actions(call):
    if call.from_user.id != ADMIN_ID: return
    bot.answer_callback_query(call.id)

    if call.data == "admin_back":
        bot.edit_message_text("Chào Admin! Bấm nút bên dưới để quản lý.", call.message.chat.id, call.message.message_id, reply_markup=admin_main_menu())

    elif call.data == "admin_add_prod":
        msg = bot.send_message(call.message.chat.id, "Nhập tên sản phẩm:", reply_markup=ForceReply(selective=True))
        bot.register_next_step_handler(msg, process_add_prod_name)

    elif call.data == "admin_add_acc":
        products = get_products()
        if not products:
            bot.edit_message_text("Kho đang trống, chưa có sản phẩm nào!", call.message.chat.id, call.message.message_id, reply_markup=back_button())
            return
        markup = InlineKeyboardMarkup()
        for key, data in products.items():
            name = data.get("name", key)
            markup.add(InlineKeyboardButton(f"➕ {name}", callback_data=f"admin_select_acc_{key}"))
        markup.add(InlineKeyboardButton("🔙 Quay Lại", callback_data="admin_back"))
        bot.edit_message_text("Bấm chọn sản phẩm muốn thêm Acc:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "admin_view_stock":
        products = get_products()
        text = "📦 **DANH SÁCH KHO**\n\n"
        if not products: 
            text += "Kho đang trống."
        else:
            for key, data in products.items():
                name = data.get("name", key)
                stock_count = len(data.get("stock", {})) if data.get("stock") else 0
                max_claims = data.get("max_claims", 1)
                text += f"🔹 **{name}**: {stock_count} acc (Vượt {data.get('links_required', 1)} link, Tối đa {max_claims} lần/ngày)\n"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=back_button())

    elif call.data == "admin_edit_prod_menu":
        products = get_products()
        if not products:
            bot.edit_message_text("Kho đang trống.", call.message.chat.id, call.message.message_id, reply_markup=back_button())
            return
        markup = InlineKeyboardMarkup()
        for key, data in products.items():
            name = data.get("name", key)
            markup.add(InlineKeyboardButton(f"⚙️ {name}", callback_data=f"admin_edit_prod_{key}"))
        markup.add(InlineKeyboardButton("🔙 Quay Lại", callback_data="admin_back"))
        bot.edit_message_text("Chọn sản phẩm muốn chỉnh sửa:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith('admin_select_acc_'):
        prod_id = call.data.split('_', 3)[3]
        products = get_products()
        prod_name = products[prod_id].get("name", prod_id)
        
        msg = bot.send_message(call.message.chat.id, f"Nhập danh sách acc cho `{prod_name}` (Mỗi dòng: user | pass):", reply_markup=ForceReply(selective=True), parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_add_acc_data, prod_id, prod_name)

    elif call.data.startswith('admin_edit_prod_'):
        prod_id = call.data.split('_', 3)[3]
        products = get_products()
        if prod_id not in products: return
        
        name = products[prod_id].get("name", prod_id)
        current_links = products[prod_id].get("links_required", 1)
        current_max = products[prod_id].get("max_claims", 1)
        
        text = (f"Đang sửa: **{name}**\n"
                f"Hiện tại: Vượt {current_links} link, Tối đa {current_max} lần/ngày.\n\n"
                f"Nhập cài đặt mới: `Số_Link | Số_Lần`")
        msg = bot.send_message(call.message.chat.id, text, reply_markup=ForceReply(selective=True), parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_edit_prod_settings, prod_id, name)

# Luồng xử lý Admin
def process_add_prod_name(message):
    name = message.text.strip()
    msg = bot.send_message(message.chat.id, f"Đã chọn: {name}\nNhập số link cần vượt (VD: 1):", reply_markup=ForceReply(selective=True))
    bot.register_next_step_handler(msg, process_add_prod_links, name)

def process_add_prod_links(message, name):
    try:
        links = int(message.text.strip())
        msg = bot.send_message(message.chat.id, f"Nhập số lần tối đa trong 1 ngày (VD: 2):", reply_markup=ForceReply(selective=True))
        bot.register_next_step_handler(msg, process_add_prod_limit, name, links)
    except:
        bot.send_message(message.chat.id, "❌ Số link không hợp lệ.", reply_markup=admin_main_menu())

def process_add_prod_limit(message, name, links):
    try:
        max_claims = int(message.text.strip())
        prod_id = str(int(time.time())) 
        requests.put(FIREBASE_URL + f"products/{prod_id}/name.json", json=name)
        requests.put(FIREBASE_URL + f"products/{prod_id}/links_required.json", json=links)
        requests.put(FIREBASE_URL + f"products/{prod_id}/max_claims.json", json=max_claims)
        bot.send_message(message.chat.id, f"✅ Đã tạo **{name}** (Vượt {links} link, Tối đa {max_claims} lần/ngày).", parse_mode='Markdown', reply_markup=admin_main_menu())
    except:
        bot.send_message(message.chat.id, "❌ Số lần không hợp lệ.", reply_markup=admin_main_menu())

def process_edit_prod_settings(message, prod_id, name):
    try:
        parts = message.text.split('|')
        links = int(parts[0].strip())
        max_claims = int(parts[1].strip())
        requests.put(FIREBASE_URL + f"products/{prod_id}/links_required.json", json=links)
        requests.put(FIREBASE_URL + f"products/{prod_id}/max_claims.json", json=max_claims)
        bot.send_message(message.chat.id, f"✅ Đã cập nhật **{name}**: Vượt {links} link, Tối đa {max_claims} lần/ngày.", parse_mode='Markdown', reply_markup=admin_main_menu())
    except:
        bot.send_message(message.chat.id, "❌ Sai định dạng.", reply_markup=admin_main_menu())

def process_add_acc_data(message, prod_id, prod_name):
    lines = message.text.strip().split('\n')
    success_count = 0
    for line in lines:
        parts = line.split('|')
        if len(parts) >= 2:
            user, pwd = parts[0].strip(), parts[1].strip()
            if user and pwd:
                requests.post(FIREBASE_URL + f"products/{prod_id}/stock.json", json={"user": user, "pass": pwd})
                success_count += 1
    if success_count > 0:
        bot.send_message(message.chat.id, f"✅ Đã thêm **{success_count}** acc vào `{prod_name}`.", parse_mode='Markdown', reply_markup=admin_main_menu())
    else:
        bot.send_message(message.chat.id, "❌ Không có acc nào được thêm.", reply_markup=admin_main_menu())

# ================= LỆNH NGƯỜI DÙNG =================
@bot.callback_query_handler(func=lambda call: call.data.startswith('user_'))
def handle_user_actions(call):
    bot.answer_callback_query(call.id)
    if call.data == "user_products":
        products = get_products()
        if not products:
            bot.send_message(call.message.chat.id, "Chưa có sản phẩm nào!")
            return
        markup = InlineKeyboardMarkup()
        for key, data in products.items():
            name = data.get("name", key)
            markup.add(InlineKeyboardButton(f"🎁 {name}", callback_data=f"buy_{key}"))
        bot.edit_message_text("Chọn sản phẩm bạn muốn nhận:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def buy_product(call):
    try:
        bot.answer_callback_query(call.id)
        prod_id = call.data.split('_', 1)[1]
        chat_id = call.message.chat.id
        products = get_products()
        
        if prod_id not in products:
             bot.send_message(chat_id, "❌ Sản phẩm không tồn tại!")
             return

        prod_name = products[prod_id].get("name", prod_id)
        max_claims = products[prod_id].get("max_claims", 1)
        
        today = get_today()
        history_res = requests.get(FIREBASE_URL + f"history/{chat_id}/{prod_id}/{today}.json")
        data_hist = history_res.json()
        claims_today = data_hist if isinstance(data_hist, int) else 0
        
        if claims_today >= max_claims:
            msg = ("❌ **Bạn đã hết lượt lấy sản phẩm này trong hôm nay!**\n\n"
                   "Vui lòng qua sản phẩm khác.\n"
                   "Bạn có thể quay lại vào sau 00:00 để tiếp tục.")
            bot.send_message(chat_id, msg, parse_mode='Markdown')
            return

        req_links = products[prod_id]["links_required"]
        requests.put(FIREBASE_URL + f"sessions/{chat_id}.json", json={"product_id": prod_id, "links_done": 0, "links_required": req_links})
        bot.delete_message(chat_id, call.message.message_id)
        generate_link4m(chat_id, prod_id, 0, req_links)
    except Exception as e:
        print("Lỗi nút bấm:", e)

# ================= NHẬN MÃ OTP =================
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
            
        prod_id = session["product_id"]
        prod_res = requests.get(FIREBASE_URL + f"products/{prod_id}.json")
        prod_data = prod_res.json()
        
        if not prod_data:
            requests.delete(FIREBASE_URL + f"otps/{otp}.json")
            bot.reply_to(message, "❌ Sản phẩm này không còn tồn tại!")
            return
            
        max_claims = prod_data.get("max_claims", 1)
        
        today = get_today()
        history_res = requests.get(FIREBASE_URL + f"history/{chat_id}/{prod_id}/{today}.json")
        data_hist = history_res.json()
        claims_today = data_hist if isinstance(data_hist, int) else 0
        
        if claims_today >= max_claims:
            requests.delete(FIREBASE_URL + f"otps/{otp}.json")
            bot.reply_to(message, "❌ **Bạn đã vượt đủ số lượng hôm nay!**\nVui lòng quay lại sau 00:00 để tiếp tục.")
            return
            
        requests.put(FIREBASE_URL + f"history/{chat_id}/{prod_id}/{today}.json", json=claims_today + 1)
        requests.delete(FIREBASE_URL + f"otps/{otp}.json") 
            
        res_acc = requests.get(FIREBASE_URL + f"products/{prod_id}/stock.json")
        stock = res_acc.json()
        
        if not stock:
            bot.reply_to(message, "❌ Kho đã hết tài khoản! Lượt vượt của bạn hôm nay đã bị trừ. Vui lòng liên hệ @mduyk để hỗ trợ.")
            return
            
        acc_key = list(stock.keys())[0]
        acc_data = stock[acc_key]
        
        requests.delete(FIREBASE_URL + f"products/{prod_id}/stock/{acc_key}.json")
        
        bot.reply_to(message, f"🎁 **TÀI KHOẢN CỦA BẠN:**\n\n`{acc_data['user']} | {acc_data['pass']}`\n\n*(Hãy copy ngay)*", parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"Lỗi: {e}")

# --- CHẠY NGẦM RESET LÚC 00:00 ---
def start_reset_thread():
    t = threading.Thread(target=reset_daily_history)
    t.daemon = True
    t.start()

def keep_alive():
    while True:
        time.sleep(600) 
        try: requests.get(RENDER_URL)
        except: pass

if __name__ == '__main__':
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"{RENDER_URL}/{BOT_TOKEN}")
    
    start_reset_thread()
    threading.Thread(target=keep_alive, daemon=True).start()
    
    app.run(host='0.0.0.0', port=3000)
