"""PyInstaller entry point for the bundled backend (launched by the Tauri app)."""

import multiprocessing

if __name__ == "__main__":
    # Must run first in a frozen app. Without it, every helper process a library spawns
    # (e.g. multiprocessing's resource_tracker) re-executes this whole program: each copy starts
    # another server and loads Whisper onto the GPU, cascading until the Mac becomes unresponsive.
    multiprocessing.freeze_support()

    from interview_agent.__main__ import main

    main()
