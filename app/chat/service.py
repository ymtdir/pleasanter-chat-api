"""
チャット処理サービス

OpenAI APIを使用したチャット機能を提供します。
内容に応じてGPT-3.5 TurboとGPT-4を切り替え、必要な場合のみファイルをアップロードします。
"""

from openai import OpenAI
from typing import Optional, List, Dict, Any
from ..config import settings
import json
import os
from pathlib import Path
import time
import re


class ChatService:
    """チャット処理サービス

    OpenAI APIを使用したチャット機能を提供するサービスクラス。
    メッセージの内容に応じてモデルとファイル送信を最適化します。
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

        # === キーワードの一元管理 ===
        # データ分析が必要なキーワード
        self.data_analysis_keywords = [
            "データ",
            "レコード",
            "件数",
            "分析",
            "統計",
            "集計",
            "傾向",
            "グラフ",
            "表",
            "一覧",
            "詳細",
            "内容",
            "構造",
            "フィールド",
            "カラム",
            "項目",
            "値",
            "取得",
            "検索",
            "抽出",
            "フィルタ",
            "合計",
            "平均",
            "最大",
            "最小",
            "比較",
            "ランキング",
            "状況",
            "状態",
            "進捗",
            "履歴",
            "変化",
            "差異",
            "どのくらい",
            "何件",
            "いくつ",
            "どんな",
            "どの",
            "どれ",
            "なぜ",
            "いつ",
            "誰",
            "どこ",
            "?",
            "？",
            "教えて",
            "おしえて",
            "まとめて",
            "分かる",
            "テーブル",
        ]

        # 複雑な処理を要求するキーワード
        self.complex_keywords = [
            "複雑",
            "詳細",
            "分析",
            "解析",
            "推論",
            "考察",
            "検討",
            "比較",
            "評価",
            "判断",
            "計算",
            "処理",
            "変換",
        ]

        # 質問パターン
        self.question_patterns = [
            r"どのくらい",
            r"何件",
            r"いくつ",
            r"どんな",
            r"どの",
            r"どれ",
            r"なぜ",
            r"いつ",
            r"誰",
            r"どこ",
            r"\?",
            r"？",
            r"どうる",
            r"教えて",
            r"おしえて",
            r"まとめて",
            r"分かる",
            r"データ",
            r"テーブル",
        ]

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

    def _get_system_prompt(self, for_data_analysis: bool = False) -> str:
        """状況に応じたシステムプロンプトを生成する

        Args:
            for_data_analysis (bool): データ分析用のプロンプトを生成するかどうか

        Returns:
            str: 生成されたシステムプロンプト
        """
        if for_data_analysis:
            return """あなたは、日本語で応答するプロのデータ分析アシスタントです。
アップロードされたJSON（プリザンターのレコード）を分析し、その内容や傾向を説明してください。

**最重要ルール:**
1. **日本語で回答:** 必ず日本語で応答してください。
2. **100文字以内:** 回答は常に100文字以内で簡潔にまとめてください。
3. **積極的な分析:** データから読み取れる傾向や特徴を積極的に見つけ出し、有用な情報を提供してください。
4. **粒度・回答速度:** 適切な粒度で30秒以内には答えてほしいです
ユーザーの質問に対し、データに基づいた洞察を分かりやすく伝えてください。"""
        else:
            return """あなたはプリザンター（Pleasanter）に関する質問に答えるアシスタントです。
回答は必ず100文字以内で、必ず日本語で簡潔に答えてください。
プリザンターの使い方、機能、設定などについて要点のみを分かりやすく回答してください。
データの詳細分析が必要な場合は、より詳細な分析を依頼するよう案内してください。"""

    def _needs_data_analysis(self, message: str) -> bool:
        """メッセージがデータ分析を必要とするかを判定

        Args:
            message (str): ユーザーメッセージ

        Returns:
            bool: データ分析が必要な場合True
        """
        message_lower = message.lower()

        # データ分析キーワードが含まれているかチェック
        for keyword in self.data_analysis_keywords:
            if keyword in message_lower:
                return True

        # 質問パターンをチェック
        for pattern in self.question_patterns:
            if re.search(pattern, message_lower):
                return True

        return False

    def _needs_gpt4(self, message: str) -> bool:
        """メッセージがGPT-4を必要とするかを判定

        Args:
            message (str): ユーザーメッセージ

        Returns:
            bool: GPT-4が必要な場合True
        """
        # データ分析が必要な場合はGPT-4を使用
        if self._needs_data_analysis(message):
            return True

        # 複雑な処理を要求するキーワード
        message_lower = message.lower()
        for keyword in self.complex_keywords:
            if keyword in message_lower:
                return True

        # メッセージが長い場合（100文字以上）はGPT-4を使用
        if len(message) > 100:
            return True

        return False

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

    async def _simple_chat(self, user_message: str) -> str:
        """シンプルなチャット（GPT-3.5 Turbo使用）

        Args:
            user_message (str): ユーザーメッセージ

        Returns:
            str: 応答メッセージ
        """
        print("[PROCESSING] GPT-3.5 Turbo でチャット処理を開始...")
        try:
            system_prompt = self._get_system_prompt(for_data_analysis=False)
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=300,
                temperature=0.7,
            )

            result = response.choices[0].message.content
            print("[SUCCESS] GPT-3.5 Turbo での処理が完了しました")
            return result

        except Exception as e:
            print(f"[ERROR] GPT-3.5 Turbo でのチャット処理に失敗: {str(e)}")
            return self.error_messages["GENERAL_ERROR"].format(error=str(e))

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
                    # プロンプトが変更されている可能性があるので更新
                    system_prompt = self._get_system_prompt(for_data_analysis=True)
                    if self.assistant.instructions != system_prompt:
                        self.assistant = self.client.beta.assistants.update(
                            assistant.id, instructions=system_prompt
                        )
                        print("[INFO] 既存アシスタントのプロンプトを更新しました。")

                    print(f"[INFO] 既存のアシスタントを使用: {self.assistant.id}")
                    return self.assistant.id

            # 見つからない場合は新規作成
            print("[INFO] 専用アシスタントが存在しないため、新規作成します。")
            system_prompt = self._get_system_prompt(for_data_analysis=True)
            self.assistant = self.client.beta.assistants.create(
                name="プリザンターデータ分析アシスタント",
                instructions=system_prompt,
                model="gpt-4o",
                tools=[{"type": "code_interpreter"}],
            )

            print(f"[SUCCESS] 新規アシスタントを作成しました: {self.assistant.id}")
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
        self, thread_id: str, run_id: str, timeout: int = 60
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

    async def _advanced_chat_with_data(self, user_message: str) -> str:
        """データ分析機能付きの高度なチャット（GPT-4 + ファイル使用）

        Args:
            user_message (str): ユーザーメッセージ

        Returns:
            str: 応答メッセージ
        """
        print("[PROCESSING] GPT-4 + ファイルアップロードで高度な分析を開始...")

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
                            print("[SUCCESS] GPT-4 での分析処理が完了しました")
                            return content.text.value

            print("[ERROR] GPT-4 からの応答取得に失敗")
            return self.error_messages["GENERAL_ERROR"].format(error="応答の取得に失敗")

        except Exception as e:
            print(f"[ERROR] GPT-4 での処理に失敗: {str(e)}")
            return self.error_messages["GENERAL_ERROR"].format(error=str(e))

    async def process_message(self, user_message: str) -> str:
        """チャットメッセージを処理

        メッセージの内容を分析して適切な処理方法を選択します：
        - データ分析が不要: GPT-3.5 Turbo でシンプルチャット
        - データ分析が必要: GPT-4 + ファイルアップロードで高度な分析

        Args:
            user_message (str): ユーザーからのメッセージ

        Returns:
            str: アシスタントからの応答またはエラーメッセージ
        """
        # クライアント初期化
        if not await self._initialize_client():
            return self.error_messages["API_KEY_INVALID"]

        print(f"[INFO] ユーザーメッセージ: {user_message}")

        # メッセージの内容に応じて処理方法を選択
        needs_gpt4 = self._needs_gpt4(user_message)
        needs_data = self._needs_data_analysis(user_message)

        print(
            f"[INFO] 判定結果 - GPT-4が必要: {needs_gpt4}, データ分析が必要: {needs_data}"
        )

        if needs_data or needs_gpt4:
            # データ分析または複雑な処理が必要な場合
            print("[MODEL] GPT-4 + ファイルアップロードで処理します")
            return await self._advanced_chat_with_data(user_message)
        else:
            # シンプルなチャットで十分な場合
            print("[MODEL] GPT-3.5 Turbo でシンプルチャットを行います")
            return await self._simple_chat(user_message)
