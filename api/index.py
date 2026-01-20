import logging
import os
from typing import Any, Dict, List, Optional # Listを追加

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

# --- メール設定 ---
mail_config = ConnectionConfig(
    MAIL_USERNAME="makanaihaishin@gmail.com",
    MAIL_PASSWORD="kujpihzkzrxpsgti",
    MAIL_FROM="makanaihaishin@gmail.com",
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

# --- データモデル ---
class SlackWebhookRequest(BaseModel):
    text: Optional[str] = Field(default=None)

# 変更点：emailを単体からリスト（配列）に変更しました
class BroadcastEmailRequest(BaseModel):
    emails: List[EmailStr] 
    count: int

# --- 関数 ---
def post_to_slack(webhook_url: str, payload: Dict[str, Any]) -> None:
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(webhook_url, json=payload)
    except Exception as e:
        logger.exception(f"Slack error: {e}")

# 追加：メール送信のバックグラウンドタスク関数
async def send_bulk_email_task(emails: List[str], count: int):
    html_content = f"""
    <div style="font-family: sans-serif; padding: 10px;">
        <p>本日はまかないが <b>{count}個</b> あります。</p>
        <p>ご利用お待ちしております！</p>
        <p><a href="https://lstep.app/hIAgXif">https://lstep.app/hIAgXif</a></p>
        <br><br>
        <p style="font-size: 0.9em; color: #555;">※購入前に、Webアプリのホーム画面右下「使い方」よりアレルギー項目の確認をお願いいたします。</p>
    </div>
    """
    
    # FastMailを使ってBCCで一括送信、または個別にループ送信
    # ここでは一般的な一斉送信（BCC）の例ですが、Gmailの制限に注意してください
    message = MessageSchema(
        subject=f"【まかないアプリ】本日は{count}食の販売があります！",
        recipients=[], # Toは空にするか、自分宛てにする
        bcc=emails,    # リストをBCCに入れることで一斉送信
        body=html_content,
        subtype=MessageType.html
    )

    fm = FastMail(mail_config)
    try:
        await fm.send_message(message)
        logger.info(f"Email sent to {len(emails)} recipients.")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

# --- APIエンドポイント ---
@app.get("/")
def root():
    return {"message": "Makanai API is running!"}

@app.post("/slack", status_code=status.HTTP_202_ACCEPTED)
def send_slack(
    background_tasks: BackgroundTasks,
    request: SlackWebhookRequest = Body(default_factory=SlackWebhookRequest),
):
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if webhook_url:
        payload = {"text": request.text or "Webhook received"}
        background_tasks.add_task(post_to_slack, webhook_url, payload)
    return {"status": "success"}

# まかない販売告知メール（一斉配信用に修正）
@app.post("/send-email")
async def send_broadcast_email(
    request: BroadcastEmailRequest, 
    background_tasks: BackgroundTasks # バックグラウンドタスクを利用
):
    # API自体はすぐにレスポンスを返し、裏でメールを送る
    background_tasks.add_task(send_bulk_email_task, request.emails, request.count)
    
    return {"status": "success", "message": f"Sending emails to {len(request.emails)} users in background."}
