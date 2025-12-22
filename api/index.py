import logging
import os
from typing import Any, Dict, Optional

import httpx
from fastapi import BackgroundTasks, Body, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

ALLOWED_ORIGINS = [
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

logger = logging.getLogger("vercel_webhook")
logging.basicConfig(level=logging.INFO)


def post_to_slack(webhook_url: str, payload: Dict[str, Any]) -> None:
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(webhook_url, json=payload)
        if response.status_code >= 400:
            logger.error(
                "Slack webhook failed: status=%s body=%s",
                response.status_code,
                response.text,
            )
    except Exception:
        logger.exception("Slack webhook request failed")


class SlackWebhookRequest(BaseModel):
    text: Optional[str] = Field(default=None, description="Slack message text")


@app.get("/")
def root() -> Dict[str, str]:
    return {
        "status": "ok",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/healthz")
def healthz() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/slack", status_code=status.HTTP_202_ACCEPTED)
def send_slack(
    background_tasks: BackgroundTasks,
    request: SlackWebhookRequest = Body(default_factory=SlackWebhookRequest),
) -> Dict[str, str]:
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SLACK_WEBHOOK_URL is not set",
        )

    default_text = "Hello from Vercel webhook"
    text = request.text
    if text is None or not text.strip():
        text = default_text
    payload = {"text": text}

    background_tasks.add_task(post_to_slack, webhook_url, payload)
    return {"status": "queued"}
