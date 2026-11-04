"""Exit when the launching app is gone, so a bundled backend never outlives the Tauri app."""

import os
import threading
import time


def parent_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def watch_parent(pid: int, interval: float = 2.0) -> None:
    def loop() -> None:
        while parent_alive(pid):
            time.sleep(interval)
        os._exit(0)

    threading.Thread(target=loop, daemon=True, name="parent-watch").start()
