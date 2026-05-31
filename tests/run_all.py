"""全テストを順に実行（Ollama不要 / GUIはオフスクリーンpump）。

  python tests\run_all.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# 各モジュールは別プロセスで実行（tkinter は 1プロセス1インタプリタに限定するため）
MODULES = [
    "test_sanitize",
    "test_config",
    "test_prompts_corpus",
    "test_integration",
    "test_clipboard",
    "test_backend_behaviors",
    "test_gui_smoke",
]


def main():
    failed = []
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    for mod in MODULES:
        print(f"\n{'='*60}\n# {mod}\n{'='*60}")
        r = subprocess.run([sys.executable, os.path.join(HERE, mod + ".py")], env=env)
        if r.returncode:
            failed.append(mod)
    print(f"\n{'='*60}")
    if failed:
        print("FAILED:", ", ".join(failed))
        sys.exit(1)
    print("ALL TEST MODULES PASSED")


if __name__ == "__main__":
    main()
