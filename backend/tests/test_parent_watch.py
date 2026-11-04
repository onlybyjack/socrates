import os
import subprocess
import sys

from interview_agent.parent_watch import parent_alive


def test_parent_alive_for_self_and_dead_pid():
    assert parent_alive(os.getpid()) is True
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    assert parent_alive(p.pid) is False
