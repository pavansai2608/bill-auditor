"""What the two disk caches share: how a key is made, and how a file is written.

There are two of them - `core/llm.py` caches model answers by prompt hash, and
`core/retrieve.py` caches searches by query. They are independent caches with
different payloads, but they must agree on two things:

**One canonical serialisation.** A key is a sha256 over a JSON dump of
everything that could change the answer. If the two caches dumped that JSON
differently, "same key discipline" would be a comment rather than a fact, and a
change to one would drift away from the other unnoticed. `key_digest` is that
serialisation, and `tests/test_llm_cache.py` pins its exact output so a change
to it cannot pass silently - every entry already on disk was addressed with it.

**One atomic write.** Both caches are written from several audit workers at
once. The temp file has to carry the writer's identity: a shared `<name>.tmp`
is a race that fails 153 times in 240 concurrent writes on one key, and the
loser raises `FileNotFoundError` out of the cache and takes its bill line down
with it. `write_json` is that write, in one place, so the second cache cannot
reintroduce the bug the first one had.
"""

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any

# path -> ((mtime_ns, size), digest). See file_digest.
_file_digests: dict[Path, tuple[tuple[int, int], str]] = {}
_file_digest_lock = threading.Lock()


def canonical(payload: Any) -> str:
    """The JSON a key is hashed over.

    Sorted keys so field order cannot change the key, and `ensure_ascii=False`
    so a rupee sign or a Devanagari character hashes as itself rather than as
    an escape sequence.
    """
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def key_digest(payload: Any) -> str:
    """sha256 over everything in `payload` that could change the answer."""
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    """sha256 of a file's bytes, recomputed only when the file changes.

    The clause index is ~350 KB and every retrieval key includes it, so hashing
    it once per search would be pure overhead on the hot path. The stat is the
    cheap check: ingestion rewrites `clauses.json` wholesale, which moves both
    its mtime and, in practice, its size.

    A missing file digests as the empty string rather than raising. Retrieval
    against an index that is not there fails on its own, with a better message
    than a cache would give.
    """
    try:
        info = path.stat()
    except OSError:
        return ""
    stamp = (info.st_mtime_ns, info.st_size)

    with _file_digest_lock:
        remembered = _file_digests.get(path)
        if remembered is not None and remembered[0] == stamp:
            return remembered[1]

    try:
        value = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""

    with _file_digest_lock:
        _file_digests[path] = (stamp, value)
    return value


def forget_file_digests() -> None:
    """Drop the memoised digests. Tests that rewrite a file on disk use this."""
    with _file_digest_lock:
        _file_digests.clear()


def write_json(path: Path, payload: Any) -> None:
    """Write `payload` to `path` atomically, safely, from any number of threads.

    The temp name carries the writer's pid and thread id. It used to be one
    shared `<name>.tmp`: two audit workers writing the same key at the same
    time, the first `replace()` consuming the file, the second raising
    `FileNotFoundError` out of the cache and failing its bill line. Six threads
    on one key failed 153 times in 240 writes.

    Whichever writer lands last wins, which is fine - concurrent writers of one
    key are storing the same answer.
    """
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident():x}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def read_json(path: Path) -> Any | None:
    """Read an entry back, or None if it is not there or is not readable.

    A half-written file must never take the system down. It is deleted, so the
    next run recomputes rather than failing on it again.
    """
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError, OSError, UnicodeDecodeError:
        path.unlink(missing_ok=True)
        return None


def store_health(directory: Path, enabled: bool, stats: dict[str, int]) -> dict[str, Any]:
    """What a cache is doing, resolved in this process rather than read off disk.

    The enable flags exist so one bill can be timed honestly, and
    docker-compose takes them from the shell, where `environment:` beats
    `env_file:`. Left exported from an earlier measurement they turn every
    repeat audit back into a cold one, and nothing says so: the page is simply
    slow again. Reading the .env cannot settle it, because the process may not
    have used that .env. This can.
    """
    try:
        entries = sum(1 for _ in directory.glob("*.json"))
    except OSError:
        entries = -1
    return {
        "enabled": enabled,
        "dir": str(directory),
        "writable": directory.exists() and os.access(directory, os.W_OK),
        "entries": entries,
        **stats,
    }
