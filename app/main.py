from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from .chat_utils import process_chat_message
from typing import List, Dict

# .env ファイルから環境変数を読み込み
load_dotenv()

# FastAPI アプリケーションの作成
app = FastAPI()

# CORSを許可（全てのオリジンから許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# リクエストボディ用のPydanticモデル
class ChatRequest(BaseModel):
    message: str


def create_chat_response(message: str) -> JSONResponse:
    """統一されたチャットレスポンスを作成"""
    return JSONResponse(content={"reply": message})


@app.post("/api/chat")
async def receive_chat(request: Request):
    """
    クライアントからのメッセージを受信し、
    ChatGPT で応答を生成して返すエンドポイント。
    """
    data = await request.json()
    user_message = data.get("message", "")

    # チャット処理をchat_utilsに委譲
    chat_reply = await process_chat_message(user_message)
    return create_chat_response(chat_reply)


@app.post("/api/items/{site_id}")
async def receive_records(site_id: int, request: Request):
    """
    各 SiteId ごとに一覧データ（レコード群）を受信
    """
    data = await request.json()
    records = data.get("records", [])

    print(f"SiteId {site_id} のレコードを受信。件数: {len(records)}")
    return JSONResponse(
        content={"status": "received", "site_id": site_id, "count": len(records)}
    )


# 開発用実行コマンド
# uvicorn app.main:app --reload
