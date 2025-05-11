from flask import Flask, request, abort
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.messaging.models import (
    TextMessage,
    QuickReply,
    QuickReplyItem,
    MessageAction,
    ReplyMessageRequest,
)
import json, os, datetime, re
from utils.inventory_utils import handle_command
from utils.inventory_utils import handle_command, get_user_sessions
user_sessions = get_user_sessions()


app = Flask(__name__)

configuration = Configuration(access_token='wtWKP5aIRl79VjNO0LueW3V+c0C4IhTUGvDlwRe2TKwBwSGwrWfP35mgSKOU7Ie2dn3G9l3b85HZxovXfliCLAQwJa9B/1omWrs8hyJOftuBydYTTEt7bZP8RPmirYWC09/3rT/AH7vfXldcOJVjHgdB04t89/1O/w1cDnyilFU=')
api_client = ApiClient(configuration=configuration)
line_bot_api = MessagingApi(api_client)
handler = WebhookHandler(channel_secret='91f81ff0defaa59d9f349fcbda672021')

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent)
def handle_message(event):
    if not isinstance(event.message, TextMessageContent):
        return

    user_text = event.message.text.strip()
    user_id = event.source.user_id

    # 銷售步驟 1：輸入商品代碼與數量
    if re.match(r"^\w+\s+\d+$", user_text) and user_sessions.get(user_id, {}).get("mode") == "sale":
        code, qty = user_text.strip().split()
        user_sessions[user_id] = {
            "mode": "sale_step_discount",
            "pending_item": {"code": code, "qty": int(qty)}
        }
        quick_reply = QuickReply(items=[
            QuickReplyItem(action=MessageAction(label="9折", text="折扣:9折")),
            QuickReplyItem(action=MessageAction(label="無折扣", text="折扣:無"))
        ])
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="請選擇折扣：", quick_reply=quick_reply)]
            )
        )
        return

    # 銷售步驟 2：選擇折扣
    if user_sessions.get(user_id, {}).get("mode") == "sale_step_discount" and user_text.startswith("折扣:"):
        user_sessions[user_id]["pending_item"]["discount_text"] = user_text.replace("折扣:", "")
        user_sessions[user_id]["mode"] = "sale_step_location"
        quick_reply = QuickReply(items=[
            QuickReplyItem(action=MessageAction(label="店面", text="通路:店面")),
            QuickReplyItem(action=MessageAction(label="網路", text="通路:網路"))
        ])
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="請選擇通路：", quick_reply=quick_reply)]
            )
        )
        return

    # 銷售步驟 3：選擇通路，完成收集
    if user_sessions.get(user_id, {}).get("mode") == "sale_step_location" and user_text.startswith("通路:"):
        item = user_sessions[user_id].pop("pending_item")
        item["location_text"] = user_text.replace("通路:", "")
        user_sessions[user_id]["mode"] = "sale"
        full_line = f"{item['code']} {item['qty']} 折扣:{item['discount_text']} 通路:{item['location_text']}"
        reply = handle_command(full_line, user_id)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )
        return

    # 功能選單快捷
    if user_text == "功能":
        quick_reply = QuickReply(items=[
            QuickReplyItem(action=MessageAction(label="查詢", text="查詢")),
            QuickReplyItem(action=MessageAction(label="銷售", text="銷售")),
            QuickReplyItem(action=MessageAction(label="退貨", text="退貨")),
            QuickReplyItem(action=MessageAction(label="贈與", text="贈與")),
            QuickReplyItem(action=MessageAction(label="調貨", text="調貨")),
            QuickReplyItem(action=MessageAction(label="補貨", text="補貨")),
            QuickReplyItem(action=MessageAction(label="總覽", text="總覽")),
            QuickReplyItem(action=MessageAction(label="結單", text="結單"))
        ])
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="請選擇功能：", quick_reply=quick_reply)]
            )
        )
        return

    # 預設其他指令由 handle_command 處理
    reply_text = handle_command(user_text, user_id)
    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=reply_text)]
        )
    )
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=5050)