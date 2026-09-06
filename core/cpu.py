"""How many threads torch may use, decided from the cgroup quota.

The defect this exists to stop: torch sizes its thread pool from
`os.cpu_count()`, which reports the *machine's* cores and knows nothing about a
container's CPU quota. In Kubernetes `retrieval-service` runs under
`limits: { cpu: "1" }` on a ten-core node, so torch started ten threads inside a
budget of one core-second per hundred-millisecond period. The threads burn the
whole quota almost immediately and are then frozen for the rest of every period.

Measured in the retrieval image at `--cpus=1`, five searches, cache off, the
harness mirroring what the service does:

                    rerank s/search   wall s/search   throttled time
    10 threads          146.25            148.35          5,368s
     2 threads          103.49            104.53            534s

1.41x, and ten times less time frozen. The work is identical either way: the
cross-encoder scored the same [48, 72, 66, 73, 70] documents in every run.

Two is the floor because two beat one. Measured separately at the same quota:
one thread 110.99s a search, two threads 95.33s. A single thread leaves the
quota partly unspent, and that costs more than some throttling does.

Nothing here assumes a container. When no quota file exists, or the quota is
unlimited, or the file says something unexpected, this falls back to
`os.cpu_count()` and behaves exactly as it did before.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

from core.config import settings
from core.logging_conf import get_logger

log = get_logger(__name__)

# cgroup v2, which is what minikube and Docker Desktop use.
CGROUP_V2 = Path("/sys/fs/cgroup/cpu.max")
# cgroup v1, still current on older hosts.
CGROUP_V1_QUOTA = Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
CGROUP_V1_PERIOD = Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us")

# Never go below this, however small the quota. See the measurement above.
MINIMUM_THREADS = 2

_applied = False


def _read(path: Path) -> str | None:
    try:
        return path.read_text().strip()
    except OSError:
        return None


def cpu_quota(
    v2: Path = CGROUP_V2,
    v1_quota: Path = CGROUP_V1_QUOTA,
    v1_period: Path = CGROUP_V1_PERIOD,
) -> tuple[float | None, str]:
    """Cores this process may use, and where that was read from.

    `None` means nothing limits us - no quota file, an unlimited quota, or a
    file whose contents do not parse. All three are the same instruction to the
    caller: fall back to the machine's core count.
    """
    raw = _read(v2)
    if raw is not None:
        fields = raw.split()
        if fields and fields[0] == "max":
            return None, f"{v2}: 'max', no quota"
        try:
            quota, period = int(fields[0]), int(fields[1])
            if quota > 0 and period > 0:
                return quota / period, f"{v2}: '{raw}'"
        except ValueError, IndexError:
            pass
        return None, f"{v2}: unparseable ({raw!r})"

    raw_quota, raw_period = _read(v1_quota), _read(v1_period)
    if raw_quota is not None and raw_period is not None:
        try:
            quota, period = int(raw_quota), int(raw_period)
            if quota > 0 and period > 0:
                return quota / period, f"{v1_quota}: '{raw_quota}/{raw_period}'"
        except ValueError:
            return None, f"{v1_quota}: unparseable ({raw_quota!r})"
        # -1 is cgroup v1 for "unlimited".
        return None, f"{v1_quota}: '{raw_quota}', no quota"

    return None, "no cgroup cpu quota file"


def thread_count(**paths: Path) -> tuple[int, str]:
    """The thread count to use, and the one-line reason for it."""
    if settings.torch_threads > 0:
        return settings.torch_threads, "BA_TORCH_THREADS"

    quota, source = cpu_quota(**paths)
    if quota is None:
        return os.cpu_count() or 1, source
    return max(MINIMUM_THREADS, math.floor(quota)), source


def set_thread_env() -> tuple[int, str]:
    """Publish the thread count into the environment. Imports nothing heavy.

    **This is the call that does the work, and it has to happen before anything
    imports torch.** `torch.set_num_threads()` on its own is not enough, and is
    actively worse than leaving it alone - measured in the retrieval image at
    `--cpus=1`, five searches:

        10 threads, untouched                        165.95s per search
        set_num_threads(2) after torch was imported   191.23s per search
        OMP_NUM_THREADS=2 set before the import       117.81s per search

    (That set was measured with a harness that imported torch at the top, which
    is what made the middle row reachable at all. The headline figures above use
    a harness that does not, because the service does not.)

    The middle row is the trap. torch reports two threads and dispatches two
    work items, but the OpenMP pool underneath was already built with ten and
    torch does not own it, so the thrash is unchanged while the parallelism is
    halved. Nothing about `torch.get_num_threads()` reveals this; only the
    clock does.

    Call it once, early, from a process that is going to load a model.
    """
    threads, source = thread_count()
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        # setdefault: an operator who set it by hand outranks us.
        os.environ.setdefault(name, str(threads))
    return threads, source


def apply_torch_threads() -> int:
    """Set the env, then tell torch as well. Safe to call repeatedly.

    Called from the two places that load a model. The env half is the one that
    matters and is only in time if nothing has imported torch yet, which is why
    the services call `set_thread_env` at start-up as well; the
    `set_num_threads` half is a backstop for the CLI and the eval, which have
    no start-up hook and where a partly-applied setting still beats none.
    """
    global _applied

    threads, source = set_thread_env()

    import torch

    if _applied:
        return torch.get_num_threads()

    torch.set_num_threads(threads)
    _applied = True
    log.info(
        "torch threads=%d (%s; os.cpu_count()=%s, torch reports %d)",
        threads,
        source,
        os.cpu_count(),
        torch.get_num_threads(),
    )
    return torch.get_num_threads()
