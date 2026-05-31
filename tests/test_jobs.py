"""Job モデルとID採番（app/jobs.py）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.jobs import Job, new_job_id, now_iso  # noqa: E402


def test_job_id_unique_and_format():
    ids = [new_job_id() for _ in range(200)]
    assert len(set(ids)) == 200, "ID重複"
    assert all(i.startswith("job-") for i in ids)


def test_now_iso_format():
    s = now_iso()
    assert "T" in s and len(s) >= 19  # YYYY-MM-DDTHH:MM:SS


def test_job_to_dict_defaults():
    j = Job("typo", "本文", source_app="app", window_title="win")
    d = j.to_dict()
    for key in ("job_id", "mode", "status", "original_text", "result_text",
                "sanitized", "error_message", "source_app", "window_title",
                "created_at", "started_at", "completed_at", "accepted"):
        assert key in d, f"欠落: {key}"
    assert d["mode"] == "typo"
    assert d["status"] == "queued"
    assert d["accepted"] is None
    assert d["result_text"] is None
    assert d["window_title"] == "win"


if __name__ == "__main__":
    test_job_id_unique_and_format()
    test_now_iso_format()
    test_job_to_dict_defaults()
    print("JOBS TESTS PASSED")
