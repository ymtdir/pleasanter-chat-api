"""
チャット処理サービス

OpenAI APIを使用したチャット機能を提供します。
Assistant APIとファイルアップロード機能を使用してJSONデータを分析します。
"""

from openai import OpenAI
from typing import Optional, List, Dict, Any
from ..config import settings
import json
import os
from pathlib import Path
import time


class ChatService:
    """チャット処理サービス

    OpenAI Assistant APIを使用したチャット機能を提供するサービスクラス。
    JSONファイルのアップロード、Assistant作成、スレッド管理を統合的に処理します。
    """

    def __init__(self, pleasanter_data: Optional[Dict[str, Any]] = None):
        """チャットサービスを初期化

        Args:
            pleasanter_data (Optional[Dict[str, Any]]): プリザンターから取得したレコードデータ（互換性のため残している）
        """
        self.pleasanter_data = pleasanter_data
        self.client = None
        self.assistant = None
        self.error_messages = {
            "API_KEY_INVALID": "OpenAI APIキーが不正または無効です。サーバーの設定をご確認ください。",
            "NO_DATA": "プリザンターデータが見つかりません。サイトIDを受信してからお試しください。",
            "GENERAL_ERROR": "エラーが発生しました: {error}",
        }

    def _get_api_key(self) -> Optional[str]:
        """OpenAI APIキーを取得

        Returns:
            Optional[str]: APIキー（未設定の場合はNone）
        """
        return settings.OPENAI_API_KEY

    def _get_latest_site_file(self) -> Optional[str]:
        """最新のサイトJSONファイルを取得

        Returns:
            Optional[str]: JSONファイルのパス（見つからない場合はNone）
        """
        data_dir = Path("data")
        if not data_dir.exists():
            return None

        json_files = list(data_dir.glob("site_*.json"))
        if not json_files:
            return None

        # 最新のファイルを取得（更新時刻ベース）
        latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
        return str(latest_file)

    async def _initialize_client(self) -> bool:
        """OpenAIクライアントを初期化

        Returns:
            bool: 初期化成功フラグ
        """
        api_key = self._get_api_key()
        if not api_key:
            return False

        self.client = OpenAI(api_key=api_key)
        return True

    async def _create_or_get_assistant(self) -> Optional[str]:
        """アシスタントを作成または取得

        Returns:
            Optional[str]: アシスタントID（失敗時はNone）
        """
        try:
            # 既存のアシスタントを検索
            assistants = self.client.beta.assistants.list()

            # プリザンター専用アシスタントを探す
            for assistant in assistants.data:
                if assistant.name == "プリザンターデータ分析アシスタント":
                    self.assistant = assistant
                    return assistant.id

            # 見つからない場合は新規作成
            self.assistant = self.client.beta.assistants.create(
                name="プリザンターデータ分析アシスタント",
                instructions="""あなたは業務アプリケーションの一覧テーブルに対して、
                その構造や内容、傾向、特徴などを分析・説明するアシスタントです。
                ユーザーに対して簡潔かつ親切に情報を提供してください。
                表以外の話題には答えず、無関係な質問には制限的に返答してください。

                アップロードされたJSONファイルはプリザンターから取得した実際のテーブルレコードです。
                このデータを詳細に分析し、ユーザーの質問に対してデータに基づく具体的な回答を提供してください。

                - データ構造を理解し、各フィールドの内容を把握してください
                - ユーザーの質問に対して、このデータから読み取れる事実のみを回答してください
                - データにない情報については推測せず、「データに含まれていません」と答えてください
                - 件数、傾向、特徴などは実際のデータを集計・分析して回答してください""",
                model="gpt-4-1106-preview",
                tools=[{"type": "code_interpreter"}],
            )

            return self.assistant.id

        except Exception as e:
            print(f"[ERROR] アシスタント作成に失敗: {str(e)}")
            return None

    async def _upload_file(self, file_path: str) -> Optional[str]:
        """JSONファイルをOpenAIにアップロード

        Args:
            file_path (str): アップロードするファイルのパス

        Returns:
            Optional[str]: ファイルID（失敗時はNone）
        """
        try:
            with open(file_path, "rb") as file:
                uploaded_file = self.client.files.create(
                    file=file, purpose="assistants"
                )
                return uploaded_file.id
        except Exception as e:
            print(f"[ERROR] ファイルアップロードに失敗: {str(e)}")
            return None

    async def _wait_for_completion(
        self, thread_id: str, run_id: str, timeout: int = 30
    ) -> bool:
        """実行完了を待機

        Args:
            thread_id (str): スレッドID
            run_id (str): 実行ID
            timeout (int): タイムアウト秒数

        Returns:
            bool: 完了フラグ
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread_id, run_id=run_id
            )

            if run.status == "completed":
                return True
            elif run.status in ["failed", "cancelled", "expired"]:
                print(f"[ERROR] 実行が失敗しました: {run.status}")
                return False

            time.sleep(1)

        print(f"[ERROR] 実行がタイムアウトしました")
        return False

    async def process_message(self, user_message: str) -> str:
        """チャットメッセージを処理

        ユーザーからのメッセージを受け取り、OpenAI Assistant APIで処理して応答を生成します。
        JSONファイルをアップロードしてアシスタントに分析させます。

        Args:
            user_message (str): ユーザーからのメッセージ

        Returns:
            str: アシスタントからの応答またはエラーメッセージ
        """
        # クライアント初期化
        if not await self._initialize_client():
            return self.error_messages["API_KEY_INVALID"]

        # 最新のJSONファイルを取得
        json_file_path = self._get_latest_site_file()
        if not json_file_path:
            return self.error_messages["NO_DATA"]

        try:
            # アシスタントの作成または取得
            assistant_id = await self._create_or_get_assistant()
            if not assistant_id:
                return self.error_messages["GENERAL_ERROR"].format(
                    error="アシスタントの作成に失敗"
                )

            # ファイルアップロード
            file_id = await self._upload_file(json_file_path)
            if not file_id:
                return self.error_messages["GENERAL_ERROR"].format(
                    error="ファイルアップロードに失敗"
                )

            # スレッド作成
            thread = self.client.beta.threads.create()

            # メッセージ追加（ファイル付き）
            self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=user_message,
                attachments=[
                    {"file_id": file_id, "tools": [{"type": "code_interpreter"}]}
                ],
            )

            # 実行開始
            run = self.client.beta.threads.runs.create(
                thread_id=thread.id, assistant_id=assistant_id
            )

            # 実行完了を待機
            if not await self._wait_for_completion(thread.id, run.id):
                return self.error_messages["GENERAL_ERROR"].format(
                    error="実行タイムアウト"
                )

            # 応答取得
            messages = self.client.beta.threads.messages.list(thread_id=thread.id)

            # 最新のアシスタントメッセージを取得
            for message in messages.data:
                if message.role == "assistant":
                    # テキストコンテンツを抽出
                    for content in message.content:
                        if content.type == "text":
                            return content.text.value

            return self.error_messages["GENERAL_ERROR"].format(error="応答の取得に失敗")

        except Exception as e:
            return self.error_messages["GENERAL_ERROR"].format(error=str(e))

    # === 後方互換性のためのメソッド（未使用） ===

    def get_system_prompt(self) -> str:
        """システムプロンプトを取得（後方互換性のため残している）"""
        return ""

    def format_user_message(self, original: str) -> str:
        """ユーザーメッセージを加工（後方互換性のため残している）"""
        return original

    def build_chat_messages(self, user_input: str) -> List[Dict[str, str]]:
        """OpenAI API用のメッセージ配列を構築（後方互換性のため残している）"""
        return []
