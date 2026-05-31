"""Job データモデル（§12.1）とID採番。"""

import datetime
import itertools
import threading

_counter = itertools.count(1)
_lock = threading.Lock()


def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")


def new_job_id():
    with _lock:
        n = next(_counter)
    return "job-" + now_iso().replace(":", "").replace("-", "") + f"-{n:03d}"


class Job:
    """§12.1 Job。MVP は逐次1件だが構造は将来の並列に耐える形。"""

    def __init__(self, mode, original_text, source_app=None, window_title=None):
        self.job_id = new_job_id()
        self.mode = mode  # "business" | "typo"
        self.status = "queued"  # queued | running | done | failed
        self.original_text = original_text
        self.result_text = None
        self.sanitized = False
        self.error_message = None
        self.source_app = source_app
        self.window_title = window_title
        self.created_at = now_iso()
        self.started_at = None
        self.completed_at = None
        self.accepted = None  # §18.3 意味保存 Y/N（True/False/None）

    def to_dict(self):
        return {
            "job_id": self.job_id,
            "mode": self.mode,
            "status": self.status,
            "original_text": self.original_text,
            "result_text": self.result_text,
            "sanitized": self.sanitized,
            "error_message": self.error_message,
            "source_app": self.source_app,
            "window_title": self.window_title,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "accepted": self.accepted,
        }
