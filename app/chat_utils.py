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
