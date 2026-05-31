#!/usr/bin/env python3
"""
Phase 0 品質検証ハーネス
========================
目的: アプリ本体を作る前に、ローカルLLM(Ollama)の補正品質が実用に足るかを測る。

仕様書 v0.2 との対応:
  - §8.4 プロンプト要件   -> PROMPTS
  - §8.5 出力サニタイズ    -> sanitize()
  - §18.3 意味保存Y/N判定  -> 対話モード or judge.py
  - §8.2 モデル候補比較    -> --model で切替、結果はモデル別に保存

使い方:
  1) Ollama を起動し、対象モデルを pull しておく
       ollama pull qwen2.5:7b-instruct-q4_K_M
  2) 生成を回す（人手判定はあとで）
       python run_phase0.py --model qwen2.5:7b-instruct-q4_K_M
  3) 別モデルでも回して比較
       python run_phase0.py --model gemma2:9b-instruct-q4_K_M
       python run_phase0.py --model gemma3:4b
  4) オーナーが実文章を10件ほど追加する場合:
       data/dummy_inputs.json の "typo"/"business" 配列に項目を足すだけ
  5) Y/N判定（意味保存できているか）:
       python run_phase0.py --judge results/<生成結果ファイル>.json

出力:
  results/gen_<model>_<timestamp>.json   生成結果（原文/生成文/サニタイズ済み）
  judge を回すと同ファイルに accepted(Y/N) と集計が追記される。
"""

import argparse
import datetime
import json
import os
import re
import sys
import urllib.request

def _resolve_data_path():
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, "data", "dummy_inputs.json"),
                 os.path.join(here, "dummy_inputs.json")):
        if os.path.exists(cand):
            return cand
    # 既定（未配置時のエラーメッセージ用）
    return os.path.join(here, "data", "dummy_inputs.json")


DATA_PATH = _resolve_data_path()
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

# --- §8.4 プロンプト ---------------------------------------------------------
PROMPTS = {
    "business": (
        "あなたは日本語のビジネス文面補正アシスタントです。\n"
        "入力文を、相手に送れる自然な依頼文として整えてください。\n\n"
        "条件:\n"
        "- 意味を変えない\n"
        "- 事実を追加しない\n"
        "- 過剰に堅くしない\n"
        "- 必要以上に長くしない\n"
        "- 依頼文として自然にする\n"
        "- 出力は修正後の本文のみ\n"
        "- 解説・前置き・引用符・箇条書きは出さない\n\n"
        "入力文:\n{input}"
    ),
    "typo": (
        "あなたは日本語の校正アシスタントです。\n"
        "入力文の誤字・脱字・誤変換・明らかな句読点の乱れだけを修正してください。\n\n"
        "条件:\n"
        "- 文体を変えない\n"
        "- 表現を言い換えない\n"
        "- 丁寧語に変えない\n"
        "- 内容を要約しない\n"
        "- 事実を追加しない\n"
        "- 改行・段落構造を維持する\n"
        "- 出力は修正後の本文のみ\n"
        "- 解説・前置き・引用符は出さない\n\n"
        "入力文:\n{input}"
    ),
}

TEMPERATURE = {"business": 0.4, "typo": 0.2}


# --- §8.5 出力サニタイズ -----------------------------------------------------
PREAMBLE_PATTERNS = [
    r"^(はい[、。]?\s*)",
    r"^(承知(いた)?しました[、。:：]?\s*)",
    r"^((修正|添削|校正)(いた)?しました[、。:：]?\s*)",
    r"^(修正(後の文|文|版|結果)?[はを]?[:：]?\s*)",
    r"^(以下が?.*?(です|になります)[:：]?\s*)",
    r"^(添削(結果)?[:：]?\s*)",
    r"^(校正(結果)?[:：]?\s*)",
]


def sanitize(text: str) -> str:
    """前置き・包み引用符・コードフェンスを除去。本文内の改行は保持する(§8.5)。"""
    if text is None:
        return ""
    t = text.strip()

    # コードフェンス除去
    if t.startswith("```"):
        t = re.sub(r"^```[^\n]*\n", "", t)
        t = re.sub(r"\n```$", "", t.rstrip())
        t = t.strip()

    # 先頭の前置き行を除去（複数回適用）
    for _ in range(3):
        before = t
        for pat in PREAMBLE_PATTERNS:
            t = re.sub(pat, "", t, flags=re.IGNORECASE)
        t = t.strip()
        if t == before:
            break

    # 全体を包む引用符を一段だけ剥がす（本文内の改行は保持）
    pairs = [("「", "」"), ("『", "』"), ('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’")]
    for open_q, close_q in pairs:
        if t.startswith(open_q) and t.endswith(close_q) and len(t) >= 2:
            t = t[len(open_q):-len(close_q)].strip()
            break

    return t


# --- Ollama 呼び出し ---------------------------------------------------------
def call_ollama(endpoint: str, model: str, prompt: str, temperature: float) -> str:
    url = endpoint.rstrip("/") + "/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body.get("response", "")


# --- 生成フェーズ -----------------------------------------------------------
def run_generation(model: str, endpoint: str):
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    records = []
    total = sum(len(data[m]) for m in ("typo", "business"))
    done = 0

    for mode in ("typo", "business"):
        for item in data[mode]:
            done += 1
            src = item["text"]
            prompt = PROMPTS[mode].format(input=src)
            print(f"[{done}/{total}] {item['id']} ({mode}) 生成中...", file=sys.stderr)
            try:
                raw = call_ollama(endpoint, model, prompt, TEMPERATURE[mode])
                clean = sanitize(raw)
                err = None
            except Exception as e:  # noqa: BLE001
                raw, clean, err = "", "", str(e)
                print(f"  -> 失敗: {e}", file=sys.stderr)

            records.append({
                "id": item["id"],
                "mode": mode,
                "degradation": item.get("degradation", []),
                "source_text": src,
                "raw_output": raw,
                "result_text": clean,
                "preamble_stripped": raw.strip() != clean and clean != "",
                "error": err,
                "accepted": None,   # §18.3 Y/N（judge で埋める）
                "note": "",
            })

    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_model = re.sub(r"[^A-Za-z0-9._-]", "_", model)
    out_path = os.path.join(RESULTS_DIR, f"gen_{safe_model}_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"model": model, "generated_at": ts, "records": records}, f,
                  ensure_ascii=False, indent=2)

    print(f"\n生成完了: {out_path}", file=sys.stderr)
    print(f"判定するには: python run_phase0.py --judge {out_path}", file=sys.stderr)
    return out_path


# --- 判定フェーズ（§18.3 意味保存 Y/N） --------------------------------------
def run_judge(path: str):
    with open(path, encoding="utf-8") as f:
        blob = json.load(f)
    records = blob["records"]

    print("\n=== 意味保存判定 (Y/N) ===")
    print("各案について、原文と意味が一致していれば y、崩れていれば n、")
    print("過剰補正(言い換え/丁寧語化/要約)が起きていれば o、スキップは Enter。\n")

    for r in records:
        if r["error"]:
            r["accepted"] = False
            r["note"] = "generation_error"
            continue
        print("-" * 60)
        print(f"[{r['id']}] mode={r['mode']} 崩れ={','.join(r['degradation'])}")
        print(f"原文 : {r['source_text']}")
        print(f"生成 : {r['result_text']}")
        ans = input("判定 [y/n/o/Enter]: ").strip().lower()
        if ans == "y":
            r["accepted"] = True
        elif ans == "n":
            r["accepted"] = False
        elif ans == "o":
            r["accepted"] = False
            r["note"] = "overcorrection"
        # Enter はそのまま None

    summarize(blob)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(blob, f, ensure_ascii=False, indent=2)
    print(f"\n保存しました: {path}")


def summarize(blob: dict):
    records = blob["records"]
    print("\n=== 集計 ===  model:", blob.get("model"))
    for mode in ("typo", "business"):
        rs = [r for r in records if r["mode"] == mode]
        judged = [r for r in rs if r["accepted"] is not None]
        yes = sum(1 for r in rs if r["accepted"] is True)
        over = sum(1 for r in rs if r.get("note") == "overcorrection")
        n = len(judged) if judged else 0
        rate = f"{yes}/{n} ({100*yes//n}%)" if n else "未判定"
        print(f"  {mode:9s} 意味保存Y: {rate}  過剰補正: {over}件")

    # 崩れ種類別の失敗集計
    fail_by_deg = {}
    for r in records:
        if r["accepted"] is False:
            for d in r["degradation"]:
                fail_by_deg[d] = fail_by_deg.get(d, 0) + 1
    if fail_by_deg:
        print("  崩れ種類別の失敗数:")
        for d, c in sorted(fail_by_deg.items(), key=lambda x: -x[1]):
            print(f"    - {d}: {c}")


def main():
    ap = argparse.ArgumentParser(description="Phase 0 品質検証ハーネス")
    ap.add_argument("--model", default="qwen2.5:7b-instruct-q4_K_M",
                    help="Ollama モデル名")
    ap.add_argument("--endpoint", default="http://localhost:11434",
                    help="Ollama エンドポイント")
    ap.add_argument("--judge", metavar="RESULT_JSON",
                    help="生成済み結果ファイルを読み込み、Y/N判定を行う")
    args = ap.parse_args()

    if args.judge:
        run_judge(args.judge)
    else:
        run_generation(args.model, args.endpoint)


if __name__ == "__main__":
    main()
