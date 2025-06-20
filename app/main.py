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
import json
import os
from pathlib import Path

# === グローバルなデータストレージ ===
# プリザンターから取得したデータを一時保存
_current_pleasanter_data = None

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

# === JSONファイル保存機能 ===


def get_data_dir() -> Path:
    """データ保存用ディレクトリを取得

    Returns:
        Path: データ保存用ディレクトリのパス
    """
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    return data_dir


def save_site_data_to_json(site_id: int, data: Dict[str, Any]) -> str:
    """サイトデータをJSONファイルに保存

    Args:
        site_id (int): サイトID
        data (Dict[str, Any]): 保存するデータ

    Returns:
        str: 保存されたファイルのパス
    """
    data_dir = get_data_dir()
    file_path = data_dir / f"site_{site_id}.json"

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return str(file_path)


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
    取得したデータはJSONファイルとして保存されます。

    処理フロー:
    1. サイトIDを受信
    2. プリザンターAPIにレコード取得リクエストを送信
    3. 取得結果をJSONファイルに保存
    4. 取得結果をログ出力およびレスポンスで返却

    Args:
        site_id (int): プリザンターのサイトID

    Returns:
        JSONResponse: 処理結果を含むレスポンス

    Success Response:
        {
            "status": "success",
            "site_id": 123,
            "message": "サイトID 123 のレコードを取得しました",
            "record_count": 25,
            "file_path": "data/site_123.json"
        }

    Error Response:
        {
            "status": "error",
            "site_id": 123,
            "message": "レコード取得に失敗しました",
            "error": "HTTPエラー: 401"
        }
    """
    print(f"[INFO] SiteId {site_id} を受信")

    # プリザンターからレコードを取得
    result = await pleasanter_client.get_records(site_id)

    if result["success"]:
        # 成功時の処理
        record_count = result.get("record_count", 0)
        print(f"[INFO] {result['message']} (件数: {record_count})")

        # 取得したデータをJSONファイルに保存
        try:
            file_path = save_site_data_to_json(site_id, result["data"])
            print(f"[INFO] データをJSONファイルに保存しました: {file_path}")
        except Exception as e:
            print(f"[ERROR] JSONファイル保存に失敗: {str(e)}")
            return create_pleasanter_response(
                success=False,
                site_id=site_id,
                message="データの保存に失敗しました",
                error=str(e),
            )

        # 取得したデータをグローバル変数に保存（従来の仕組みも維持）
        global _current_pleasanter_data
        _current_pleasanter_data = result["data"]

        return create_pleasanter_response(
            success=True,
            site_id=site_id,
            message=result["message"],
            record_count=record_count,
            file_path=file_path,
        )
    else:
        # 失敗時の処理
        print(f"[ERROR] {result['message']}: {result['error']}")

        return create_pleasanter_response(
            success=False,
            site_id=site_id,
            message=result["message"],
            error=result["error"],
        )


@app.post("/api/test-processing-message")
async def test_processing_message(
    chat_service: ChatService = Depends(get_chat_service),
) -> JSONResponse:
    """処理中メッセージのテスト送信エンドポイント

    Returns:
        JSONResponse: テスト結果
    """
    print("[INFO] 処理中メッセージのテスト送信開始")

    # テスト用のテーブル関連メッセージ
    test_message = "テーブルの件数を教えて"

    # ChatServiceの処理中メッセージ送信をテスト
    result = await chat_service._send_processing_message(test_message)

    if result:
        return JSONResponse(
            content={
                "status": "success",
                "message": f"処理中メッセージをサイトID {result} に送信しました",
                "test_message": test_message,
            }
        )
    else:
        return JSONResponse(
            content={
                "status": "error",
                "message": "処理中メッセージの送信に失敗しました",
                "test_message": test_message,
            },
            status_code=500,
        )


@app.post("/api/send-message/{site_id}")
async def send_message_to_pleasanter(
    site_id: int,
    request: Request,
    pleasanter_client: PleasanterClient = Depends(get_pleasanter_client),
) -> JSONResponse:
    """プリザンターにメッセージを送信するエンドポイント

    指定されたサイトIDにメッセージを送信します。
    処理中メッセージや任意のメッセージを送信できます。

    Args:
        site_id (int): プリザンターのサイトID
        request (Request): HTTPリクエスト（messageパラメータを含む）

    Returns:
        JSONResponse: 送信結果を含むレスポンス

    Example:
        Request: {"message": "処理中です。しばらくお待ちください。"}
        Response: {"status": "success", "site_id": 123, "message": "メッセージを送信しました"}
    """
    data = await request.json()
    message = data.get("message", "")

    if not message:
        return create_pleasanter_response(
            success=False,
            site_id=site_id,
            message="送信するメッセージが指定されていません",
            error="message parameter is required",
        )

    print(f"[INFO] SiteId {site_id} にメッセージを送信: {message}")

    # プリザンターにメッセージを送信
    result = await pleasanter_client.send_message(site_id, message)

    if result["success"]:
        print(f"[INFO] {result['message']}")
        return create_pleasanter_response(
            success=True, site_id=site_id, message=result["message"]
        )
    else:
        print(f"[ERROR] {result['message']}: {result['error']}")
        return create_pleasanter_response(
            success=False,
            site_id=site_id,
            message=result["message"],
            error=result["error"],
        )


# === 開発用コマンド ===
# uvicorn app.main:app --reload
