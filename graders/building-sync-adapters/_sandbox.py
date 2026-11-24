"""Limits on the model-written code that the probes import and run.

The probes run answer code (a fake session, a retry client) inside the grader
process. ``lib.run_probe`` starts them with an empty environment, so no API
key or token is in reach. ``confine`` then installs an audit hook that refuses:

- starting a process (``subprocess``, ``os.system``, ``os.exec*``, spawn, fork);
- a network connection or a DNS lookup;
- writing, renaming or removing a file outside ``writable_root``.

An audit hook is not a security boundary: code that sets out to escape it can.
It stops answer code from reaching the network, the runner's files or a
subprocess by ordinary means, and it fails the trial loudly when it tries.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_SPAWN = (
    "subprocess.Popen",
    "os.system",
    "os.exec",
    "os.posix_spawn",
    "os.spawn",
    "os.fork",
    "os.forkpty",
    "pty.spawn",
)
_NETWORK = ("socket.connect", "socket.getaddrinfo", "socket.gethostbyname")
_FILE_CHANGES = ("os.remove", "os.rename", "os.rmdir", "os.mkdir", "shutil.rmtree")
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC


def confine(writable_root: Path) -> None:
    """Install the audit hook. Call it before importing any answer code."""
    root = str(writable_root.resolve())

    def inside(path: object) -> bool:
        try:
            resolved = os.path.realpath(os.fsdecode(path))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False
        return resolved == root or resolved.startswith(root + os.sep)

    def hook(event: str, args: tuple) -> None:
        if event.startswith(_SPAWN):
            raise PermissionError(f"the grader sandbox refuses {event}")
        if event in _NETWORK:
            raise PermissionError(f"network access is blocked in the grader ({event})")
        if event == "open" and args:
            path, mode, flags = (list(args) + [None, None])[:3]
            writes = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
                isinstance(flags, int) and flags & _WRITE_FLAGS
            )
            if writes and not isinstance(path, int) and not inside(path):
                raise PermissionError(f"the grader sandbox refuses a write to {path}")
        if event in _FILE_CHANGES and args and not inside(args[0]):
            raise PermissionError(f"the grader sandbox refuses {event} on {args[0]}")

    sys.addaudithook(hook)
