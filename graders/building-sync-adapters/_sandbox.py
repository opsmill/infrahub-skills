"""Limits on the model-written code that the probes import and run.

The probes run answer code (a fake session, a retry client) inside the grader
process. ``lib.run_probe`` starts them with an empty environment, so no API
key or token is in reach. ``confine`` then installs an audit hook that refuses:

- starting a process (``subprocess``, ``os.system``, ``os.exec*``, spawn, fork);
- a network connection, a datagram send or a DNS lookup;
- writing, truncating, renaming, linking, removing or changing the mode of
  a file outside ``writable_root``, and any of these relative to a
  directory descriptor, whose target the hook cannot resolve;
- changing the mode or the owner of a file through a descriptor, because a
  read-only descriptor can point outside ``writable_root``.

The ``open`` audit event carries no directory descriptor, so ``confine`` also
replaces ``os.open`` with a wrapper that refuses a write relative to one.

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
_NETWORK = (
    "socket.connect",
    "socket.sendto",
    "socket.sendmsg",
    "socket.getaddrinfo",
    "socket.gethostbyname",
)
# event: (indexes of the paths it changes, indexes of its directory descriptors)
_FILE_CHANGES: dict[str, tuple[tuple[int, ...], tuple[int, ...]]] = {
    "os.remove": ((0,), (1,)),
    "os.rmdir": ((0,), (1,)),
    "os.mkdir": ((0,), (2,)),
    "os.truncate": ((0,), ()),
    "os.chmod": ((0,), (2,)),
    "os.chown": ((0,), (3,)),
    # a symlink only names its target; writing through it reaches the open check
    "os.symlink": ((1,), (2,)),
    # a hard link to an outside file would let a write inside change it
    "os.link": ((0, 1), (2, 3)),
    # os.rename and os.replace: both the source and the destination
    "os.rename": ((0, 1), (2, 3)),
    "shutil.rmtree": ((0,), (1,)),
}
# a read-only descriptor of an outside file is enough to change its mode or owner
_NO_FD = ("os.chmod", "os.chown")
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
        if event in _FILE_CHANGES:
            paths, dir_fds = _FILE_CHANGES[event]
            for i in dir_fds:
                if i < len(args) and args[i] not in (None, -1):
                    raise PermissionError(
                        f"the grader sandbox refuses {event} relative to a directory descriptor"
                    )
            for i in paths:
                if i < len(args) and isinstance(args[i], int) and event in _NO_FD:
                    raise PermissionError(
                        f"the grader sandbox refuses {event} through a descriptor"
                    )
                # truncate needs a descriptor opened for writing, which the open
                # check above already confined
                if (
                    i < len(args)
                    and not isinstance(args[i], int)
                    and not inside(args[i])
                ):
                    raise PermissionError(
                        f"the grader sandbox refuses {event} on {args[i]}"
                    )

    sys.addaudithook(hook)

    real_open = os.open

    def confined_open(path, flags, mode=0o777, *, dir_fd=None):  # noqa: ANN001, ANN202
        if dir_fd is not None and flags & _WRITE_FLAGS:
            raise PermissionError(
                "the grader sandbox refuses a write relative to a directory descriptor"
            )
        return real_open(path, flags, mode, dir_fd=dir_fd)

    os.open = confined_open
