"""
プリザンターAPI連携モジュール

プリザンターのREST APIに接続してレコード情報を取得する機能を提供します。
認証、エラーハンドリング、レスポンス形式の統一化を行います。
"""

import httpx
from typing import Dict, Any, Optional
from ..config import settings


class PleasanterClient:
    """プリザンターAPIクライアント

    プリザンターのREST APIとの通信を担当するクライアントクラス。
    APIキー認証、リクエスト送信、エラーハンドリングを統一的に処理します。
    """

    def __init__(self):
        """プリザンターAPIクライアントを初期化

        設定からプリザンターサーバーの接続情報を取得し、
        クライアントインスタンスを構成します。
        """
        self.base_url = settings.PLEASANTER_BASE_URL
        self.api_key = settings.PLEASANTER_API_KEY
        self.timeout = 30.0  # リクエストタイムアウト（秒）

    def _build_request_data(self) -> Dict[str, Any]:
        """プリザンターAPI用のリクエストデータを構築

        Returns:
            Dict[str, Any]: APIリクエスト用のデータ辞書

        Raises:
            ValueError: APIキーが設定されていない場合
        """
        if not self.api_key:
            raise ValueError("PLEASANTER_API_KEY環境変数が設定されていません")

        return {"ApiKey": self.api_key}

    def _parse_response_data(self, response_json: Dict[str, Any]) -> int:
        """レスポンスデータからレコード件数を取得

        Args:
            response_json: プリザンターAPIのレスポンスJSON

        Returns:
            int: 取得したレコード件数
        """
        try:
            return len(response_json.get("Response", {}).get("Data", []))
        except (AttributeError, TypeError):
            return 0

    async def get_records(self, site_id: int) -> Dict[str, Any]:
        """指定されたサイトIDのレコードを取得

        プリザンターAPIの/api/items/{site_id}/getエンドポイントを呼び出し、
        指定されたサイトのレコード一覧を取得します。

        Args:
            site_id (int): プリザンターのサイトID

        Returns:
            Dict[str, Any]: 処理結果を含む辞書
                success (bool): 成功/失敗フラグ
                data (Dict): レスポンスデータ（成功時のみ）
                message (str): 処理結果メッセージ
                record_count (int): 取得レコード件数（成功時のみ）
                error (str): エラー詳細（失敗時のみ）
        """
        url = f"{self.base_url}/api/items/{site_id}/get"

        try:
            # リクエストデータの構築
            request_data = self._build_request_data()

            # HTTPクライアントでAPI呼び出し
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=request_data,
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout,
                )

                # レスポンスの処理
                if response.status_code == 200:
                    response_json = response.json()
                    record_count = self._parse_response_data(response_json)

                    return {
                        "success": True,
                        "data": response_json,
                        "message": f"サイトID {site_id} のレコードを取得しました",
                        "record_count": record_count,
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTPエラー: {response.status_code}",
                        "message": f"サイトID {site_id} のレコード取得に失敗しました",
                        "details": response.text,
                    }

        except ValueError as e:
            # APIキー未設定エラー
            return {
                "success": False,
                "error": str(e),
                "message": "APIキーの設定を確認してください",
            }
        except httpx.TimeoutException:
            # タイムアウトエラー
            return {
                "success": False,
                "error": "タイムアウト",
                "message": "プリザンターサーバーへの接続がタイムアウトしました",
            }
        except Exception as e:
            # その他の予期しないエラー
            return {
                "success": False,
                "error": str(e),
                "message": f"予期しないエラーが発生しました: {str(e)}",
            }
