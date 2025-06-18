"""
FastAPI メインアプリケーション

プリザンター連携チャットAPIのメインエントリポイント。
チャット機能とプリザンター連携機能のHTTPエンドポイントを提供します。

Endpoints:
    POST /api/chat: ChatGPTを使用したチャット機能
    POST /api/site-id/{site_id}: プリザンターサイトIDの受信とレコード取得
"""

from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .dependencies import get_chat_service, get_pleasanter_client
from .chat.service import ChatService
from .pleasanter.client import PleasanterClient
from typing import Dict, Any

# FastAPIアプリケーションの作成
app = FastAPI()

# CORS設定 - 全てのオリジンからのアクセスを許可
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切なドメインに制限することを推奨
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === 依存性プロバイダー ===


def get_pleasanter_client() -> PleasanterClient:
    """プリザンターAPIクライアントを取得

    依存性注入用のプロバイダー関数。
    エンドポイントで必要な時にPleasanterAPIインスタンスを作成して提供します。

    Returns:
        PleasanterAPI: 設定済みのプリザンターAPIクライアント
    """
    return PleasanterClient()


# === リクエスト/レスポンス モデル ===


class ChatRequest(BaseModel):
    """チャットリクエストのデータモデル

    Attributes:
        message (str): ユーザーからのメッセージ
    """

    message: str


# === ユーティリティ関数 ===


def create_chat_response(message: str) -> JSONResponse:
    """統一されたチャットレスポンスを作成

    チャット機能で使用する標準的なJSONレスポンス形式を生成します。
    エラー時も正常時も同じ形式で統一されています。

    Args:
        message (str): レスポンスメッセージ

    Returns:
        JSONResponse: {"reply": "メッセージ"} 形式のレスポンス
    """
    return JSONResponse(content={"reply": message})


def create_pleasanter_response(
    success: bool, site_id: int, message: str, **kwargs
) -> JSONResponse:
    """プリザンター関連のレスポンスを作成

    プリザンター連携機能で使用する標準的なレスポンス形式を生成します。

    Args:
        success (bool): 処理成功フラグ
        site_id (int): 対象のサイトID
        message (str): レスポンスメッセージ
        **kwargs: 追加データ（record_count, errorなど）

    Returns:
        JSONResponse: 処理結果を含むレスポンス
    """
    content = {
        "status": "success" if success else "error",
        "site_id": site_id,
        "message": message,
        **kwargs,
    }
    status_code = 200 if success else 500
    return JSONResponse(content=content, status_code=status_code)


# === APIエンドポイント ===


@app.post("/api/chat")
async def receive_chat(
    request: Request, chat_service: ChatService = Depends(get_chat_service)
) -> JSONResponse:
    """チャットメッセージ処理エンドポイント

    クライアントからのメッセージを受信し、ChatGPTで応答を生成して返します。
    OpenAI APIキーが未設定の場合は、エラーメッセージを返却します。

    Args:
        request (Request): HTTPリクエスト

    Returns:
        JSONResponse: {"reply": "応答メッセージ"} 形式のレスポンス

    Example:
        Request: {"message": "プリザンターについて教えて"}
        Response: {"reply": "プリザンターは..."}
    """
    data = await request.json()
    user_message = data.get("message", "")

    # DI されたサービスを使用
    chat_reply = await chat_service.process_message(user_message)
    return create_chat_response(chat_reply)


@app.post("/api/site-id/{site_id}")
async def receive_site_id(
    site_id: int, pleasanter_client: PleasanterClient = Depends(get_pleasanter_client)
) -> JSONResponse:
    """プリザンターサイトID受信エンドポイント

    プリザンター側からサイトIDの通知を受信し、
    そのサイトのレコード情報をプリザンターAPIから取得します。

    処理フロー:
    1. サイトIDを受信
    2. プリザンターAPIにレコード取得リクエストを送信
    3. 取得結果をログ出力およびレスポンスで返却

    Args:
        site_id (int): プリザンターのサイトID

    Returns:
        JSONResponse: 処理結果を含むレスポンス

    Success Response:
        {
            "status": "success",
            "site_id": 123,
            "message": "サイトID 123 のレコードを取得しました",
            "record_count": 25
        }

    Error Response:
        {
            "status": "error",
            "site_id": 123,
            "message": "レコード取得に失敗しました",
            "error": "HTTPエラー: 401"
        }
    """
    print(f"📨 SiteId {site_id} を受信")

    # プリザンターからレコードを取得
    result = await pleasanter_client.get_records(site_id)

    if result["success"]:
        # 成功時の処理
        record_count = result.get("record_count", 0)
        print(f"✅ {result['message']} (件数: {record_count})")

        return create_pleasanter_response(
            success=True,
            site_id=site_id,
            message=result["message"],
            record_count=record_count,
        )
    else:
        # 失敗時の処理
        print(f"❌ {result['message']}: {result['error']}")

        return create_pleasanter_response(
            success=False,
            site_id=site_id,
            message=result["message"],
            error=result["error"],
        )


# === 開発用コマンド ===
# uvicorn app.main:app --reload
