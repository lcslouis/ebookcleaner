"""
Background download task management.

DownloadTask  — a single fetch-and-save job (one book / one update).
DownloadManager — holds all tasks, emits signals for UI updates.

_FetchWorker is defined here (moved out of fetch_dialog) so both
the foreground dialog and background tasks share the same worker.
"""
import time
import threading
import uuid
import sys
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QThread
import requests as _requests


# ------------------------------------------------------------------ screen-wake helper

def _keep_awake(active: bool) -> None:
    """Prevent screen saver / display sleep while downloads run (Windows only)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ES_CONTINUOUS       = 0x80000000
        ES_SYSTEM_REQUIRED  = 0x00000001
        ES_DISPLAY_REQUIRED = 0x00000002
        flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED if active else 0)
        ctypes.windll.kernel32.SetThreadExecutionState(flags)
    except Exception:
        pass


# ------------------------------------------------------------------ worker

class _FetchSignals(QObject):
    chapter_done = Signal(int, int, str)   # index, total, title
    status_update = Signal(str)            # retry / backoff messages
    finished = Signal(list)               # [{title, content, url, error}]
    error = Signal(str)
    blocked_403 = Signal(str, str)         # url, chapter_title


class _FetchWorker(QThread):
    def __init__(self, fetcher, chapter_list):
        super().__init__()
        self.fetcher = fetcher
        self.chapter_list = chapter_list
        self.signals = _FetchSignals()
        self._cancelled   = False
        self._pause_event = threading.Event()
        self._pause_event.set()   # not paused initially
        self._skip_blocked = False

    def cancel(self):
        self._cancelled = True
        self._pause_event.set()   # unblock any waiting thread

    def resume(self, skip: bool = False):
        """Resume after a 403 pause. Pass skip=True to drop the chapter."""
        self._skip_blocked = skip
        self._pause_event.set()

    def run(self):
        results = []
        total = len(self.chapter_list)
        for i, ch in enumerate(self.chapter_list):
            if self._cancelled:
                break
            content, err = self._fetch_with_retry(ch["url"], ch["title"], i + 1, total)
            if err:
                content = f"[Chapter could not be downloaded: {err}]"
            results.append({"title": ch["title"], "content": content,
                            "url": ch["url"], "error": err})
            self.signals.chapter_done.emit(i + 1, total, ch["title"])
        self.signals.finished.emit(results)

    def _fetch_with_retry(self, url: str, title: str, idx: int, total: int):
        """Fetch one chapter with retries. Returns (content, error_msg)."""
        max_retries = 3
        last_err = None

        for attempt in range(max_retries + 1):
            if self._cancelled:
                return "", "Cancelled"
            try:
                return self.fetcher.fetch_chapter(url), None
            except _requests.exceptions.HTTPError as e:
                code = e.response.status_code if e.response is not None else 0
                if code == 403:
                    # Pause and let the user open a browser / solve CAPTCHA
                    self.signals.blocked_403.emit(url, title)
                    self._pause_event.clear()
                    self._pause_event.wait()   # blocks until resume() or cancel()
                    if self._cancelled:
                        return "", "Cancelled"
                    if self._skip_blocked:
                        self._skip_blocked = False
                        return "", "403 Forbidden — skipped by user"
                    self._pause_event.set()    # re-arm for the next potential block
                    # Retry once after the user has handled it
                    try:
                        return self.fetcher.fetch_chapter(url), None
                    except Exception as retry_e:
                        return "", str(retry_e)
                if code == 404:
                    return "", "404 Not Found"
                if code == 429:
                    if attempt < max_retries:
                        wait = 10 * (2 ** attempt)   # 10 s, 20 s, 40 s
                        self.signals.status_update.emit(
                            f"Rate limited — waiting {wait}s before retry "
                            f"({idx}/{total}: {title[:30]}…)"
                        )
                        time.sleep(wait)
                        last_err = f"429 rate limit (retry {attempt + 1})"
                        continue
                    return "", "429 Too Many Requests — rate limited"
                if 500 <= code < 600:
                    if attempt < max_retries:
                        wait = 5 * (2 ** attempt)    # 5 s, 10 s, 20 s
                        self.signals.status_update.emit(
                            f"Server error {code} — retrying in {wait}s "
                            f"({idx}/{total}: {title[:30]}…)"
                        )
                        time.sleep(wait)
                        last_err = str(e)
                        continue
                    return "", f"Server error {code}"
                return "", str(e)
            except (_requests.exceptions.ConnectionError,
                    _requests.exceptions.Timeout) as e:
                if attempt < max_retries:
                    wait = 5 * (2 ** attempt)
                    self.signals.status_update.emit(
                        f"Connection error — retrying in {wait}s "
                        f"({idx}/{total}: {title[:30]}…)"
                    )
                    time.sleep(wait)
                    last_err = str(e)
                    continue
                return "", f"Connection error: {e}"
            except Exception as e:
                return "", str(e)

        return "", last_err or "Unknown error"


# ------------------------------------------------------------------ task

class DownloadTask(QObject):
    """Self-contained fetch-and-save job.  Created by FetchDialog; owned by
    DownloadManager once handed off for background execution."""

    progress_changed = Signal(int, int, str)   # done, total, current_title
    completed = Signal(str)                    # task_id
    failed = Signal(str, str)                  # task_id, error_msg
    blocked_403 = Signal(str, str, str)        # task_id, url, chapter_title

    STATUS_RUNNING   = "running"
    STATUS_DONE      = "done"
    STATUS_ERROR     = "error"
    STATUS_CANCELLED = "cancelled"
    STATUS_BLOCKED   = "blocked"

    def __init__(self, *, db, fetcher, selected_chapters, toc_info,
                 update_book_id=None, cover_data=b"", cover_mime="image/jpeg",
                 custom_title="", custom_author="", source_url=""):
        super().__init__()
        self.task_id       = uuid.uuid4().hex[:8]
        self.db            = db
        self.fetcher       = fetcher
        self.selected_chapters = selected_chapters
        self.toc_info      = toc_info or {}
        self.update_book_id = update_book_id
        self.cover_data    = cover_data
        self.cover_mime    = cover_mime
        self.custom_title  = custom_title
        self.custom_author = custom_author
        self.source_url    = source_url
        self.book_title    = custom_title or self.toc_info.get("title") or "Unknown"

        self.status        = self.STATUS_RUNNING
        self.done_count    = 0
        self.total_count   = len(selected_chapters)
        self.failed_count  = 0
        self.current_chapter = ""
        self.error_msg     = ""
        self.result_book_id: int = 0

        self._worker = _FetchWorker(fetcher, selected_chapters)
        self._worker.signals.chapter_done.connect(self._on_chapter_done)
        self._worker.signals.status_update.connect(self._on_status_update)
        self._worker.signals.finished.connect(self._on_finished)
        self._worker.signals.error.connect(self._on_error)
        self._worker.signals.blocked_403.connect(self._on_blocked_403)

    def start(self):
        self._worker.start()

    def cancel(self):
        self._worker.cancel()
        self.status = self.STATUS_CANCELLED

    # ------------------------------------------------------------------ slots

    def _on_chapter_done(self, idx, total, title):
        self.done_count = idx
        self.current_chapter = title
        self.progress_changed.emit(idx, total, title)

    def _on_status_update(self, msg):
        self.current_chapter = msg
        self.progress_changed.emit(self.done_count, self.total_count, msg)

    def _on_finished(self, results):
        self.failed_count = sum(1 for ch in results if ch.get("error"))
        try:
            self._save(results)
            self.status = self.STATUS_DONE
            self.completed.emit(self.task_id)
        except Exception as e:
            self.status = self.STATUS_ERROR
            self.error_msg = str(e)
            self.failed.emit(self.task_id, str(e))

    def _on_blocked_403(self, url: str, title: str):
        self.status = self.STATUS_BLOCKED
        self.blocked_403.emit(self.task_id, url, title)

    def resume_after_403(self, skip: bool = False):
        self.status = self.STATUS_RUNNING
        self._worker.resume(skip=skip)

    def _on_error(self, msg):
        self.status = self.STATUS_ERROR
        self.error_msg = msg
        self.failed.emit(self.task_id, msg)

    # ------------------------------------------------------------------ save

    def _save(self, chapter_results):
        if self.update_book_id:
            self._save_update(chapter_results)
        else:
            self._save_new(chapter_results)

    def _save_new(self, chapter_results):
        info = self.toc_info
        title       = self.custom_title  or info.get("title")       or "Untitled"
        author      = self.custom_author or info.get("author")       or ""
        description = info.get("description") or ""
        cover_url   = info.get("cover_url")   or ""

        book_id = self.db.add_book(title, author, description,
                                   source_url=self.source_url, cover_url=cover_url)
        if self.cover_data:
            ext = "jpg" if "jpeg" in self.cover_mime else self.cover_mime.split("/")[-1]
            covers_dir = Path.home() / ".ebookcleaner" / "covers"
            covers_dir.mkdir(parents=True, exist_ok=True)
            (covers_dir / f"{book_id}.{ext}").write_bytes(self.cover_data)

        for i, ch in enumerate(chapter_results, start=1):
            self.db.add_chapter(book_id, i, ch["title"], ch["content"],
                                source_url=ch.get("url", ""))

        version_num = self.db.get_next_version_number(book_id)
        self.db.add_version(book_id, version_num, self.source_url,
                            len(chapter_results), notes="Fetched from web")
        self.result_book_id = book_id

    def _save_update(self, chapter_results):
        book_id      = self.update_book_id
        existing_urls = self.db.get_chapter_source_urls(book_id)

        if existing_urls:
            new_chapters = [ch for ch in chapter_results
                            if not (ch.get("url") and ch["url"] in existing_urls)]
        else:
            # No stored URLs — dialog pre-filtered to new chapters only
            new_chapters = chapter_results

        if new_chapters:
            start_num = self.db.get_max_chapter_number(book_id) + 1
            for i, ch in enumerate(new_chapters):
                self.db.add_chapter(book_id, start_num + i, ch["title"], ch["content"],
                                    source_url=ch.get("url", ""))
            book = self.db.get_book(book_id)
            update_fields = {"title": book["title"]}
            if self.source_url and not book.get("source_url"):
                update_fields["source_url"] = self.source_url
            self.db.update_book(book_id, **update_fields)
            version_num = self.db.get_next_version_number(book_id)
            self.db.add_version(book_id, version_num, self.source_url, len(new_chapters),
                                notes=f"Update: {len(new_chapters)} new chapter(s) added")

        self.result_book_id = book_id


# ------------------------------------------------------------------ manager

class DownloadManager(QObject):
    """Owns all DownloadTask objects; UI widgets observe this object."""

    task_added           = Signal(object)   # DownloadTask
    tasks_changed        = Signal()
    active_count_changed = Signal(int)
    book_saved           = Signal(int)      # book_id — refresh the library list
    task_blocked_403     = Signal(object, str, str)   # task, url, title

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks: list = []

    # ------------------------------------------------------------------ public

    def add_task(self, task: DownloadTask):
        was_idle = self.active_count() == 0
        task.progress_changed.connect(lambda *_: self.tasks_changed.emit())
        task.completed.connect(self._on_task_done)
        task.failed.connect(lambda _tid, _msg: self._on_task_failed())
        task.blocked_403.connect(self._on_task_blocked_403)
        self._tasks.insert(0, task)
        task.start()
        if was_idle:
            _keep_awake(True)
        self.task_added.emit(task)
        self.tasks_changed.emit()
        self.active_count_changed.emit(self.active_count())

    def cancel_task(self, task_id: str):
        for t in self._tasks:
            if t.task_id == task_id:
                t.cancel()
                break
        if self.active_count() == 0:
            _keep_awake(False)
        self.tasks_changed.emit()
        self.active_count_changed.emit(self.active_count())

    def get_tasks(self) -> list:
        return list(self._tasks)

    def active_count(self) -> int:
        return sum(1 for t in self._tasks
                   if t.status in (DownloadTask.STATUS_RUNNING, DownloadTask.STATUS_BLOCKED))

    def clear_finished(self):
        self._tasks = [t for t in self._tasks
                       if t.status == DownloadTask.STATUS_RUNNING]
        self.tasks_changed.emit()

    # ------------------------------------------------------------------ private

    def _on_task_done(self, task_id: str):
        for t in self._tasks:
            if t.task_id == task_id and t.result_book_id:
                self.book_saved.emit(t.result_book_id)
                break
        if self.active_count() == 0:
            _keep_awake(False)
        self.tasks_changed.emit()
        self.active_count_changed.emit(self.active_count())

    def _on_task_blocked_403(self, task_id: str, url: str, title: str):
        for t in self._tasks:
            if t.task_id == task_id:
                self.task_blocked_403.emit(t, url, title)
                break
        self.tasks_changed.emit()
        self.active_count_changed.emit(self.active_count())

    def _on_task_failed(self):
        if self.active_count() == 0:
            _keep_awake(False)
        self.tasks_changed.emit()
        self.active_count_changed.emit(self.active_count())
