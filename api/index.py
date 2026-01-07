import logging
import os
from typing import Any, Dict, Optional

import httpx
from fastapi import BackgroundTasks, Body, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from pydantic import BaseModel, EmailStr, Field

app = FastAPI()

# Bubbleからのアクセスを許可
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("vercel_webhook")
logging.basicConfig(level=logging.INFO)

# --- メール設定 (Vercelの環境変数から読み込む) ---
mail_config = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME", ""),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", ""),
    MAIL_FROM="makanaihaishin@gmail.com",      
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

# --- データモデル ---
# Slack用（変更なし）
class SlackWebhookRequest(BaseModel):
    text: Optional[str] = Field(default=None)

# メール用（ここを変更しました！）
class BroadcastEmailRequest(BaseModel):
    email: EmailStr # 送り先のメールアドレス
    count: int      # まかないの個数（xx個）

# --- 関数 ---
def post_to_slack(webhook_url: str, payload: Dict[str, Any]) -> None:
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(webhook_url, json=payload)
    except Exception as e:
        logger.exception(f"Slack error: {e}")

# --- APIエンドポイント ---
@app.get("/")
def root():
    return {"message": "Makanai API is running!"}

# Slack通知（変更なし）
@app.post("/slack", status_code=status.HTTP_202_ACCEPTED)
def send_slack(
    background_tasks: BackgroundTasks,
    request: SlackWebhookRequest = Body(default_factory=SlackWebhookRequest),
):
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if webhook_url:
        text = request.text or "Webhook received"
        background_tasks.add_task(post_to_slack, webhook_url, {"text": text})
    return {"status": "queued"}

# まかない販売告知メール (New!)
@app.post("/send-email", status_code=status.HTTP_202_ACCEPTED)
async def send_broadcast_email(
    background_tasks: BackgroundTasks,
    request: BroadcastEmailRequest
):

    #メール配信用文章
    html_content = f"""
    <div style="font-family: sans-serif; padding: 10px;">
        <p>本日はまかないが <b>{request.count}個</b> あります。</p>
        <p>ご利用お待ちしております！</p>
        <p>
            <a href="https://lstep.app/hIAgXif">https://lstep.app/hIAgXif</a>
        </p>
        <br>
        <br>
        <p style="font-size: 0.9em; color: #555;">
            ※購入前に、Webアプリのホーム画面右下「使い方」よりアレルギー項目の確認をお願いいたします。
        </p>
    </div>
    """
    
    message = MessageSchema(
        subject=f"【まかないアプリ】本日は{request.count}食の販売があります！",
        recipients=[request.email],
        body=html_content,
        subtype=MessageType.html
    )

    fm = FastMail(mail_config)
    background_tasks.add_task(fm.send_message, message)
    return {"status": "broadcast_queued"}
