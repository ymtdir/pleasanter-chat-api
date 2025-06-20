"""
FastAPI依存性プロバイダー

各サービスのインスタンス生成を統一的に管理します。
"""

from .chat.service import ChatService
from .pleasanter.client import PleasanterClient


def get_chat_service() -> ChatService:
    """チャットサービスを取得

    Returns:
        ChatService: 設定済みのチャットサービス
    """
    # JSONファイルベースのアプローチに変更されたため、
    # グローバル変数からのデータ取得は不要になりました
    # ChatServiceは自動的に最新のJSONファイルを検索します
    return ChatService()


def get_pleasanter_client() -> PleasanterClient:
    """プリザンターAPIクライアントを取得

    Returns:
        PleasanterClient: 設定済みのプリザンターAPIクライアント
    """
    return PleasanterClient()
