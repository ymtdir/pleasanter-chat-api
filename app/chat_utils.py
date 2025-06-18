from openai import OpenAI
import os
from typing import Optional
from .config import settings

# エラーメッセージ定数
ERROR_MESSAGES = {
    "API_KEY_INVALID": "APIキーが不正または無効です。APIサーバーの設定をご確認ください。",
    "GENERAL_ERROR": "エラーが発生しました: {error}",
}


def get_system_prompt() -> str:
    """
    ChatGPTに与えるシステムプロンプト（性格・振る舞いの指示）を返す。
    """
    prompt = (
        "あなたは丁寧で親しみやすい日本語を話すアシスタントです。\n"
        "以下のルールを厳格に守ってください：\n"
        "- あなたの専門領域はプリザンター業務システムのみです。\n"
        "- 回答は必ずプリザンターに関する内容に限定してください。\n"
        "- プリザンターと関係のない話題には「その件についてはお答えできません」と返答してください。\n"
    )
    return prompt


def format_user_message(original: str) -> str:
    """
    ユーザーからの入力にルールや制約を加えて加工する。
    例：文字数や表現ルールの追加。
    """
    instructions = """
        以下の制約に従って答えてください：
        - 30字以内で簡潔に
        - 専門用語は避けてわかりやすく
    """
    return f"{original.strip()}\n\n{instructions.strip()}"


def build_chat_messages(user_input: str) -> list[dict]:
    """
    ChatGPTに渡すmessages配列を生成する。
    """
    return [
        {"role": "system", "content": get_system_prompt()},
        {"role": "user", "content": format_user_message(user_input)},
    ]


def get_openai_api_key() -> Optional[str]:
    """OpenAI APIキーを取得"""
    return settings.OPENAI_API_KEY


async def process_chat_message(user_message: str) -> str:
    """
    チャットメッセージを処理してOpenAI APIから応答を取得
    APIキーの検証からレスポンス生成まで全て処理
    """
    # APIキーの検証
    api_key = get_openai_api_key()
    if not api_key:
        return ERROR_MESSAGES["API_KEY_INVALID"]

    try:
        # OpenAI API呼び出し
        client = OpenAI(api_key=api_key)
        messages = build_chat_messages(user_message)

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
        )

        return response.choices[0].message.content

    except Exception as e:
        return ERROR_MESSAGES["GENERAL_ERROR"].format(error=str(e))
