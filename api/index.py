import logging
import os
from typing import Any, Dict, Optional

import httpx
from fastapi import BackgroundTasks, Body, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from pydantic import BaseModel, EmailStr, Field
from typing import List

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

# --- メール設定（ここが重要：行の左端に寄せています） ---
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

class BroadcastEmailRequest(BaseModel):
    emails: List[EmailStr] # <-- List[]で囲むことで配列を受け取れます
    count: int

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

# Slack通知
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

# --- エンドポイントの修正 ---
@app.post("/send-email")
async def send_broadcast_email(
    request: BroadcastEmailRequest, 
    background_tasks: BackgroundTasks # バックグラウンドタスクを利用
):
    # メール作成ロジックを関数化（またはここで直接定義）
    html_content = f"""
    <div style="font-family: sans-serif; padding: 10px;">
        <p>本日はまかないが <b>{request.count}個</b> あります。</p>
        <p>お早めにご利用ください！</p>
    </div>
    """
    
    message = MessageSchema(
        subject=f"【まかないアプリ】本日は{request.count}食の販売があります！",
        recipients=["makanaihaishin@gmail.com"], # TOは自分（管理者）宛てにする
        bcc=request.emails,    # 【重要】リストはBCCに入れる！
        body=html_content,
        subtype=MessageType.html
    )

    fm = FastMail(mail_config)
    
    # APIは「受付完了」と即答し、裏でメールを送る
    background_tasks.add_task(fm.send_message, message)
    
    return {"status": "success", "message": f"Queued {len(request.emails)} emails."}
