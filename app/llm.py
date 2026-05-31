"""Local LLM Client（§8.1 Ollama）。外部API送信は禁止。

stdlib のみ（urllib）。接続不可・タイムアウト・モデル不在を区別して例外化する。
"""

import json
import urllib.error
import urllib.request


class LLMError(Exception):
    """LLM呼び出しの失敗。kind で種別を区別する。"""

    def __init__(self, message, kind="generic"):
        super().__init__(message)
        self.kind = kind  # "connection" | "timeout" | "model" | "generic"


def list_models(endpoint, timeout=5):
    """Ollama にインストール済みのモデル名一覧を返す（接続確認も兼ねる）。"""
    url = endpoint.rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise LLMError(f"Ollama に接続できません: {e}", kind="connection")
    except Exception as e:  # noqa: BLE001
        raise LLMError(f"モデル一覧の取得に失敗: {e}", kind="generic")
    return [m.get("name", "") for m in body.get("models", []) if m.get("name")]


def check_connection(endpoint, timeout=5):
    """接続可能なら True。例外は投げない（§11.4 起動可・状態表示用）。"""
    try:
        list_models(endpoint, timeout=timeout)
        return True
    except LLMError:
        return False


def generate(endpoint, model, prompt, temperature, timeout=120, think=None):
    """補正案を1件生成して文字列で返す。失敗時は LLMError。

    think: True/False を渡すと Ollama の思考(thinking)を明示制御する（Qwen3等）。
           None なら指定しない。思考モデルは False で大幅に高速化する。
    """
    url = endpoint.rstrip("/") + "/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": float(temperature)},
    }
    if think is not None:
        payload["think"] = bool(think)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "ignore")
        except Exception:  # noqa: BLE001
            pass
        if e.code == 404 or "model" in detail.lower():
            raise LLMError(
                f"モデル '{model}' が見つかりません。ollama pull が必要です。",
                kind="model",
            )
        raise LLMError(f"生成に失敗しました (HTTP {e.code}): {detail}", kind="generic")
    except urllib.error.URLError as e:
        raise LLMError(
            f"ローカルLLMに接続できませんでした。Ollama/設定を確認してください ({e}).",
            kind="connection",
        )
    except TimeoutError:
        raise LLMError("生成がタイムアウトしました。", kind="timeout")

    if "error" in body:
        return _raise_body_error(body["error"], model)
    return body.get("response", "")


def _raise_body_error(message, model):
    if "model" in str(message).lower():
        raise LLMError(
            f"モデル '{model}' が見つかりません。ollama pull が必要です。",
            kind="model",
        )
    raise LLMError(f"生成に失敗しました: {message}", kind="generic")
