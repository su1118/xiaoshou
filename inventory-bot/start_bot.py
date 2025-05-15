import subprocess
import time
import requests
import os

# ======= 設定你的 LINE Channel Access Token =======
LINE_CHANNEL_ACCESS_TOKEN = "wtWKP5aIRl79VjNO0LueW3V+c0C4IhTUGvDlwRe2TKwBwSGwrWfP35mgSKOU7Ie2dn3G9l3b85HZxovXfliCLAQwJa9B/1omWrs8hyJOftuBydYTTEt7bZP8RPmirYWC09/3rT/AH7vfXldcOJVjHgdB04t89/1O/w1cDnyilFU="
# ================================================

# 1. 啟動 ngrok
print("正在啟動 ngrok...")
ngrok = subprocess.Popen(["ngrok", "http", "5000"], stdout=subprocess.DEVNULL)
time.sleep(3)  # 等待 ngrok 建立隧道

# 2. 取得 ngrok public URL
try:
    tunnel_info = requests.get("http://localhost:4040/api/tunnels").json()
    public_url = tunnel_info['tunnels'][0]['public_url']
    print(f"ngrok Public URL：{public_url}")
except Exception as e:
    print("無法取得 ngrok 公網網址，請檢查 ngrok 是否正確啟動")
    public_url = None

# 3. 啟動 Flask 應用
print("正在啟動 app.py（Flask 伺服器）...")
subprocess.Popen(["python", "app.py"])
print("Flask 伺服器已啟動")

# 4. 設定 LINE Webhook
if public_url:
    webhook_url = f"{public_url}/callback"
    print(f"正在設定 LINE Webhook URL：{webhook_url}")
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    body = {
        "endpoint": webhook_url
    }
    response = requests.put(
        "https://api.line.me/v2/bot/channel/webhook/endpoint",
        headers=headers,
        json=body
    )
    if response.status_code == 200:
        print("Webhook 設定成功")
    else:
        print("Webhook 設定失敗，回應：", response.text)

    # 啟用 Webhook（確保已打開 webhook 的使用）
    response_enable = requests.post(
        "https://api.line.me/v2/bot/channel/webhook/endpoint/enable",
        headers=headers
    )
    if response_enable.status_code == 200:
        print("Webhook 已啟用")
    else:
        print("Webhook 啟用失敗，回應：", response_enable.text)
else:
    print("無法設定 Webhook，ngrok 公網網址取得失敗")