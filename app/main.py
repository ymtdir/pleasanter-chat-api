from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
import os
from dotenv import load_dotenv
from .chat_utils import build_chat_messages
from typing import List, Dict

# .env ファイルから環境変数を読み込み
load_dotenv()

# OpenAI クライアントの初期化
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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


@app.post("/api/chat")
async def receive_chat(request: Request):
    """
    クライアントからのメッセージを受信し、
    ChatGPT で応答を生成して返すエンドポイント。
    """
    data = await request.json()
    user_message = data.get("message", "")

    try:
        messages = build_chat_messages(user_message)

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
        )

        chat_reply = response.choices[0].message.content
        return JSONResponse(content={"reply": chat_reply})

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post("/api/items/{site_id}")
async def receive_records(site_id: int, request: Request):
    """
    各 SiteId ごとに一覧データ（レコード群）を受信
    """
    data = await request.json()
    records = data.get("records", [])

    print(f"SiteId {site_id} のレコードを受信。件数: {len(records)}")
    # ここでDBに保存したり、ログ記録などの処理を追加可能
    return JSONResponse(
        content={"status": "received", "site_id": site_id, "count": len(records)}
    )


# 開発用実行コマンド
# uvicorn app.main:app --reload
