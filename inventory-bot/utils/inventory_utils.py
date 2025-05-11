import json, os, datetime
import re
INVENTORY_FILE = 'inventory.json'
STAFF_FILE = 'staff.json'
LOG_FILE = 'log.txt'

# 暫存銷售資料（模擬簡單 session 機制）
user_sessions = {}

def get_user_sessions():
    return user_sessions


# 輔助方法
def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def write_log(entry):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{entry}\n")

# 指令處理主入口
# 指令處理主入口（已修正流程路徑與補貨、新增、調貨的誤判問題）
def handle_command(text, user_id):
    mode = user_sessions.get(user_id, {}).get("mode")

    # 指令起始階段
    if text == "查詢":
        return "請輸入商品名稱或代碼："
    elif text.startswith("查 " ):
        return query_item(text[2:].strip())
    elif text == "銷售":
        user_sessions[user_id] = {"mode": "sale", "items": []}
        return "請輸入商品代碼與數量"
    elif text == "調貨":
        user_sessions[user_id] = {"mode": "transfer", "items": []}
        return "請輸入要調貨的商品代碼與數量（如 CL0001 2）\n完成後輸入「完成」"
    elif text == "補貨":
        user_sessions[user_id] = {"mode": "restock", "items": []}
        return "請輸入補貨商品代碼與數量（如 CU0003 4）\n完成後輸入「完成」"
    elif text == "退貨":
        user_sessions[user_id] = {"mode": "return", "items": []}
        return "請輸入退貨商品代碼與數量（如 CL0001 1）\n完成後輸入「完成」"
    elif text == "贈與":
        user_sessions[user_id] = {"mode": "gift", "items": []}
        return "請輸入要贈送的商品代碼與數量（如 CU0003 2）\n完成後輸入「完成」"
    elif text.startswith("新增 "):
        return add_new_item(text[3:].strip())
    elif text == "結單":
        return monthly_summary()
    elif text == "總覽":
        return overview_inventory()

    # 流程中：完成階段
    elif text == "完成":
        if mode == "gift":
            user_sessions[user_id]["mode"] = "gift_name"
            return "請輸入贈與人姓名："
        elif mode in ("sale", "transfer", "restock", "return"):
            return "請輸入人員代碼（三位數）："
        else:
            return "⚠️ 尚未開始任何操作流程"

    # 流程中：輸入人員代碼階段
    elif text.isdigit() and len(text) == 3:
        if mode == "sale":
            return finalize_sale(user_id, text)
        elif mode == "transfer":
            return finalize_transfer(user_id, text)
        elif mode == "restock":
            return finalize_restock(user_id, text)
        elif mode == "return":
            return finalize_return(user_id, text)

    # 流程中：依據模式解析商品內容
    elif user_id in user_sessions:
        if mode == "sale":
            return collect_sale_items(user_id, text)
        elif mode == "transfer":
            return collect_transfer_items(user_id, text)
        elif mode == "restock":
            return collect_restock_items(user_id, text)
        elif mode == "return":
            return collect_return_items(user_id, text)
        elif mode == "gift":
            return collect_gift_items(user_id, text)
        elif mode == "gift_name":
            return finalize_gift(user_id, text)

    return "❓ 指令錯誤或無法識別，請重新輸入。"


# 查詢單一商品
def query_item(keyword):
    data = load_json(INVENTORY_FILE)
    for code, item in data.items():
        if keyword == code or keyword == item['name']:
            return (f"🔍 商品資訊：\n"
                    f"名稱：{item['name']}\n"
                    f"代碼：{item['code']}\n"
                    f"價格：{item['price']}\n"
                    f"店面庫存：{item['center']}\n"
                    f"倉庫庫存：{item['warehouse']}")
    return "查無此商品，請確認輸入的名稱或代碼是否正確。"

# 收集商品輸入（使用折扣:9折 通路:店面 格式）
def collect_sale_items(user_id, text):
    def parse_sale_line(line):
        code_qty_match = re.search(r"(\w+)\s+(\d+)", line)
        discount_match = re.search(r"折扣[:：]?(9折|無)", line)
        location_match = re.search(r"通路[:：]?(店面|網路)", line)

        if code_qty_match:
            code = code_qty_match.group(1)
            qty = int(code_qty_match.group(2))
            discount = 0.9 if discount_match and discount_match.group(1) == "9折" else 1
            location = location_match.group(1) if location_match else "店面"
            return {"code": code, "qty": qty, "discount": discount, "location": location}
        return None

    lines = text.strip().split('\n')
    items = []
    for line in lines:
        parsed = parse_sale_line(line)
        if parsed:
            items.append(parsed)
    user_sessions[user_id]["items"] = items
    return "✅ 已加入商品，輸入「完成」結束輸入"

# 確認人員代碼後處理銷售（新版邏輯）
def finalize_sale(user_id, staff_code):
    if not os.path.exists(STAFF_FILE):
        return "未找到人員資料，請聯絡管理員"
    staff_list = load_json(STAFF_FILE)
    if staff_code not in staff_list:
        return "❌ 人員代碼錯誤"

    data = load_json(INVENTORY_FILE)
    session = user_sessions.get(user_id, {})
    items = session.get("items", [])

    result_lines = ["🧾 銷售結果："]
    total = 0
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for item in items:
        code = item['code']
        qty = item['qty']
        discount = item['discount']
        location = item['location']

        if code not in data:
            result_lines.append(f"❌ 未找到商品代碼：{code}")
            continue
        stock_item = data[code]
        if stock_item['center'] < qty:
            result_lines.append(f"❌ 庫存不足：{code} 僅剩 {stock_item['center']}")
            continue

        price = int(stock_item['price'] * qty * discount)
        stock_item['center'] -= qty
        total += price

        result_lines.append(
            f"{stock_item['name']} ({code}) x{qty} ➤ NT${price} ({location})\n店面剩餘：{stock_item['center']} 件"
        )
        write_log(f"{timestamp}|販售|{code}|{qty}|{price}|{staff_code}|{location}")

    save_json(INVENTORY_FILE, data)
    user_sessions.pop(user_id, None)
    result_lines.append(f"\n💰 總金額：NT${total}")
    return '\n'.join(result_lines)
# 總覽
def overview_inventory():
    data = load_json(INVENTORY_FILE)
    if not data:
        return "目前無商品資料。"

    result = ["📦 所有商品總覽："]
    for code, item in data.items():
        result.append(f"{item['name']} ({code})\n價格：{item['price']}\n店面庫存：{item['center']}、倉庫庫存：{item['warehouse']}\n")
    return '\n'.join(result)

# 結單統計
def monthly_summary():
    if not os.path.exists(LOG_FILE):
        return "尚無銷售紀錄。"

    now = datetime.datetime.now()
    current_month = now.strftime("%Y-%m")
    total = 0
    product_stats = {}

    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if '販售' in line and current_month in line:
                try:
                    parts = line.strip().split('|')
                    code = parts[2]  # 商品代碼
                    qty = int(parts[3])  # 數量
                    amount = int(parts[4])  # 金額
                    total += amount
                    if code not in product_stats:
                        product_stats[code] = 0
                    product_stats[code] += qty
                except:
                    continue

    if total == 0:
        return "本月尚無銷售資料。"

    result = [f"📊 本月總銷售額：NT${total}", "🧾 商品銷售統計："]
    for code, qty in product_stats.items():
        result.append(f"{code} x{qty}")
    return '\n'.join(result)


#調貨
def collect_transfer_items(user_id, text):
    lines = text.strip().split('\n')
    items = []
    for line in lines:
        if ' ' in line:
            parts = line.strip().split(' ')
            if len(parts) == 2:
                code, qty = parts[0], int(parts[1])
                items.append((code, qty))
    user_sessions[user_id]["items"] = items
    return "✅ 已加入調貨清單，輸入「完成」結束輸入"

# finalize 調貨邏輯
def finalize_transfer(user_id, staff_code):
    if not os.path.exists(STAFF_FILE):
        return "未找到人員資料，請聯絡管理員"
    staff_list = load_json(STAFF_FILE)
    if staff_code not in staff_list:
        return "❌ 人員代碼錯誤"

    data = load_json(INVENTORY_FILE)
    session = user_sessions.get(user_id, {})
    items = session.get("items", [])
    result_lines = ["📦 調貨結果："]
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for code, qty in items:
        if code not in data:
            result_lines.append(f"❌ 無此商品：{code}")
            continue
        item = data[code]
        if item['warehouse'] < qty:
            result_lines.append(f"❌ 倉庫庫存不足：{code} 目前有 {item['warehouse']}")
            continue

        item['warehouse'] -= qty
        item['center'] += qty
        result_lines.append(
            f"{item['name']} ({code}) ➤ 倉庫 ➜ 店面 x{qty}\n倉庫剩餘：{item['warehouse']}、店面現在：{item['center']}"
        )
        write_log(f"{timestamp}|調貨|{code}|{qty}|0|{staff_code}|倉轉店")

    save_json(INVENTORY_FILE, data)
    user_sessions.pop(user_id, None)
    return '\n'.join(result_lines)

# 收集補貨輸入
def collect_restock_items(user_id, text):
    lines = text.strip().split('\n')
    items = []
    for line in lines:
        if ' ' in line:
            parts = line.strip().split(' ')
            if len(parts) == 2:
                code, qty = parts[0], int(parts[1])
                items.append((code, qty))
    user_sessions[user_id]["items"] = items
    return "✅ 已加入補貨清單，輸入「完成」結束輸入"

# finalize 補貨邏輯
def finalize_restock(user_id, staff_code):
    if not os.path.exists(STAFF_FILE):
        return "未找到人員資料，請聯絡管理員"
    staff_list = load_json(STAFF_FILE)
    if staff_code not in staff_list:
        return "❌ 人員代碼錯誤"

    data = load_json(INVENTORY_FILE)
    session = user_sessions.get(user_id, {})
    items = session.get("items", [])
    result_lines = ["📦 補貨結果："]
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for code, qty in items:
        if code not in data:
            result_lines.append(f"❌ 無此商品：{code}")
            continue
        item = data[code]
        item['warehouse'] += qty
        result_lines.append(f"{item['name']} ({code}) ➤ 補入倉庫 x{qty}\n倉庫現在：{item['warehouse']}")
        write_log(f"{timestamp}|補貨|{code}|{qty}|0|{staff_code}|補入倉")

    save_json(INVENTORY_FILE, data)
    user_sessions.pop(user_id, None)
    return '\n'.join(result_lines)


# 收集贈與輸入
def collect_gift_items(user_id, text):
    lines = text.strip().split('\n')
    items = []
    for line in lines:
        if ' ' in line:
            parts = line.strip().split(' ')
            if len(parts) == 2:
                code, qty = parts[0], int(parts[1])
                items.append((code, qty))
    user_sessions[user_id]["items"] = items
    return "✅ 已加入贈與清單，輸入「完成」結束輸入"

# finalize_gift 處理邏輯
def finalize_gift(user_id, giver_name):
    data = load_json(INVENTORY_FILE)
    session = user_sessions.get(user_id, {})
    items = session.get("items", [])
    result_lines = ["🎁 贈與結果："]
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for code, qty in items:
        if code not in data:
            result_lines.append(f"❌ 無此商品：{code}")
            continue
        item = data[code]
        if item['center'] < qty:
            result_lines.append(f"❌ 店面庫存不足：{code} 目前僅有 {item['center']}")
            continue

        item['center'] -= qty
        result_lines.append(f"{item['name']} ({code}) ➤ 贈出 x{qty}\n店面剩餘：{item['center']} 件")
        write_log(f"{timestamp}|贈與|{code}|{qty}|0|{giver_name}|贈出")

    save_json(INVENTORY_FILE, data)
    user_sessions.pop(user_id, None)
    return '\n'.join(result_lines)


# 收集退貨項目
def collect_return_items(user_id, text):
    lines = text.strip().split('\n')
    items = []
    for line in lines:
        if ' ' in line:
            parts = line.strip().split(' ')
            if len(parts) == 2:
                code, qty = parts[0], int(parts[1])
                items.append((code, qty))
    user_sessions[user_id]["items"] = items
    return "✅ 已加入退貨清單，輸入「完成」結束輸入"

# finalize_return 處理邏輯
def finalize_return(user_id, staff_code):
    if not os.path.exists(STAFF_FILE):
        return "未找到人員資料，請聯絡管理員"
    staff_list = load_json(STAFF_FILE)
    if staff_code not in staff_list:
        return "❌ 人員代碼錯誤"

    data = load_json(INVENTORY_FILE)
    session = user_sessions.get(user_id, {})
    items = session.get("items", [])
    result_lines = ["↩️ 退貨結果："]
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for code, qty in items:
        if code not in data:
            result_lines.append(f"❌ 無此商品：{code}")
            continue
        item = data[code]
        item['center'] += qty
        result_lines.append(f"{item['name']} ({code}) ➤ 退回店面 x{qty}\n店面現在：{item['center']} 件")
        write_log(f"{timestamp}|退貨|{code}|{qty}|0|{staff_code}|退貨")

    save_json(INVENTORY_FILE, data)
    user_sessions.pop(user_id, None)
    return '\n'.join(result_lines)

# 新增商品邏輯：新增 商品名稱 商品代碼 價格 倉庫庫存

def add_new_item(line):
    parts = line.strip().split(' ')
    if len(parts) != 4:
        return "❌ 格式錯誤，請輸入格式：新增 商品名稱 商品代碼 價格 倉庫庫存"

    name, code, price_str, stock_str = parts
    try:
        price = int(price_str)
        stock = int(stock_str)
    except:
        return "❌ 價格與庫存需為數字"

    data = load_json(INVENTORY_FILE)
    if code in data:
        return "⚠️ 此商品代碼已存在"

    data[code] = {
        "name": name,
        "code": code,
        "price": price,
        "center": 0,
        "warehouse": stock
    }

    save_json(INVENTORY_FILE, data)
    return f"✅ 已新增商品：{name} ({code})\n價格：{price}\n初始倉庫庫存：{stock}"