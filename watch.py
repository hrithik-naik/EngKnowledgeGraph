import time
from pathlib import Path

from watchdog.observers.polling import PollingObserver as Observer
from watchdog.events import FileSystemEventHandler

from ingest import main as run_ingest


class DataDirectoryHandler(FileSystemEventHandler):
    def __init__(self, cooldown_seconds: float = 1.5):
        self.cooldown_seconds = cooldown_seconds
        self.last_trigger_time = 0.0

    def on_modified(self, event):
        if event.is_directory:
            return

        if not event.src_path.endswith((".yml", ".yaml")):
            return

        now = time.time()
        if now - self.last_trigger_time < self.cooldown_seconds:
            return

        self.last_trigger_time = now
        print(f"[WATCHER] Change detected: {event.src_path}", flush=True)

        try:
            run_ingest()
        except Exception as e:
            # Never let watcher thread die
            print(f"[WATCHER] Ingest failed: {e}", flush=True)


def start_watcher(data_dir: Path):
    print("[WATCHER] Initial ingest", flush=True)

    # First-run reconciliation (critical)
    try:
        run_ingest()
    except Exception as e:
        print(f"[WATCHER] Initial ingest failed: {e}", flush=True)

    print(f"[WATCHER] Starting watcher on {data_dir}", flush=True)

    observer = Observer()
    observer.schedule(
        DataDirectoryHandler(cooldown_seconds=1.5),
        str(data_dir),
        recursive=False,
    )
    observer.start()

    print(f"[WATCHER] Watching directory: {data_dir}", flush=True)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[WATCHER] Stopping watcher", flush=True)
        observer.stop()

    observer.join()


if __name__ == "__main__":
    start_watcher(Path("data"))
