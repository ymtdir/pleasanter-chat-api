"""
チャット処理サービス

OpenAI APIを使用したチャット機能を提供します。
プロンプト生成、メッセージ加工、API呼び出しを統合的に処理します。
"""

from openai import OpenAI
from typing import Optional, List, Dict, Any
from ..config import settings


class ChatService:
    """チャット処理サービス

    OpenAI APIを使用したチャット機能を提供するサービスクラス。
    システムプロンプト生成、ユーザーメッセージ加工、API呼び出しを統合的に処理します。
    """

    def __init__(self):
        """チャットサービスを初期化"""
        self.error_messages = {
            "API_KEY_INVALID": "OpenAI APIキーが不正または無効です。サーバーの設定をご確認ください。",
            "GENERAL_ERROR": "エラーが発生しました: {error}",
        }

    def get_system_prompt(self) -> str:
        """システムプロンプトを取得

        ChatGPTに与えるシステムプロンプト（性格・振る舞いの指示）を返します。
        プリザンター専門のアシスタントとしての役割を定義します。

        Returns:
            str: システムプロンプト文字列
        """
        return (
            "あなたは丁寧で親しみやすい日本語を話すアシスタントです。\n"
            "以下のルールを厳格に守ってください：\n"
            "- あなたの専門領域はプリザンター業務システムのみです。\n"
            "- 回答は必ずプリザンターに関する内容に限定してください。\n"
            "- プリザンターと関係のない話題には「その件についてはお答えできません」と返答してください。\n"
        )

    def format_user_message(self, original: str) -> str:
        """ユーザーメッセージを加工

        ユーザーからの入力にルールや制約を加えて加工します。
        回答の品質と形式を統一するための指示を追加します。

        Args:
            original (str): 元のユーザーメッセージ

        Returns:
            str: 加工されたメッセージ
        """
        instructions = """
        以下の制約に従って答えてください：
        - 30字以内で簡潔に
        - 専門用語は避けてわかりやすく
        """
        return f"{original.strip()}\n\n{instructions.strip()}"

    def build_chat_messages(self, user_input: str) -> List[Dict[str, str]]:
        """OpenAI API用のメッセージ配列を構築

        システムプロンプトとユーザーメッセージを組み合わせて、
        OpenAI APIに送信するためのメッセージ配列を生成します。

        Args:
            user_input (str): ユーザーからの入力メッセージ

        Returns:
            List[Dict[str, str]]: OpenAI API用のメッセージ配列
        """
        return [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": self.format_user_message(user_input)},
        ]

    def _get_api_key(self) -> Optional[str]:
        """OpenAI APIキーを取得

        設定からOpenAI APIキーを取得します。

        Returns:
            Optional[str]: APIキー（未設定の場合はNone）
        """
        return settings.OPENAI_API_KEY

    async def process_message(self, user_message: str) -> str:
        """チャットメッセージを処理

        ユーザーからのメッセージを受け取り、OpenAI APIで処理して応答を生成します。
        APIキーの検証、プロンプト構築、API呼び出し、エラーハンドリングを統合的に処理します。

        Args:
            user_message (str): ユーザーからのメッセージ

        Returns:
            str: ChatGPTからの応答またはエラーメッセージ
        """
        # APIキーの検証
        api_key = self._get_api_key()
        if not api_key:
            return self.error_messages["API_KEY_INVALID"]

        try:
            # OpenAI API呼び出し
            client = OpenAI(api_key=api_key)
            messages = self.build_chat_messages(user_message)

            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
            )

            return response.choices[0].message.content

        except Exception as e:
            return self.error_messages["GENERAL_ERROR"].format(error=str(e))
