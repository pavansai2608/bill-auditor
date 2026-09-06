"""The thread count torch is given, decided from the cgroup quota.

The defect: torch sizes its pool from `os.cpu_count()`, which reports the
machine's cores and knows nothing about a container's CPU quota. In Kubernetes
`retrieval-service` runs under `limits: { cpu: "1" }` on a ten-core node, so
torch started ten threads inside one core's budget and spent almost every
scheduling period frozen.

Every case here is decided from a file written into a temporary directory, not
from the machine this runs on. A test that reads the real `/sys/fs/cgroup`
would pass on a laptop, pass in a container, and prove nothing in either.
"""

import os
import tempfile
import unittest
from pathlib import Path

from core import cpu
from core.config import settings


class QuotaToThreadsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        # The override is a setting, so it has to be put back or the next test
        # in the suite inherits it.
        self.addCleanup(setattr, settings, "torch_threads", settings.torch_threads)
        settings.torch_threads = 0

    def paths(self, *, v2: str | None = None, quota: str | None = None, period: str | None = None):
        """Only the files a case actually wants exist. The rest are absent."""
        places = {
            "v2": self.dir / "cpu.max",
            "v1_quota": self.dir / "cpu.cfs_quota_us",
            "v1_period": self.dir / "cpu.cfs_period_us",
        }
        for key, text in (("v2", v2), ("v1_quota", quota), ("v1_period", period)):
            if text is not None:
                places[key].write_text(text)
        return places

    @property
    def unlimited(self) -> int:
        return os.cpu_count() or 1

    def test_a_one_core_quota_gets_two_threads(self):
        """Two, not one. Measured: 95.33s a search at two, 110.99s at one."""
        self.assertEqual(cpu.thread_count(**self.paths(v2="100000 100000"))[0], 2)

    def test_a_four_core_quota_gets_four_threads(self):
        self.assertEqual(cpu.thread_count(**self.paths(v2="400000 100000"))[0], 4)

    def test_max_means_no_quota(self):
        threads, why = cpu.thread_count(**self.paths(v2="max 100000"))
        self.assertEqual(threads, self.unlimited)
        self.assertIn("max", why)

    def test_a_bare_max_is_also_no_quota(self):
        """Not the documented shape, but it must not read as unparseable."""
        threads, why = cpu.thread_count(**self.paths(v2="max"))
        self.assertEqual(threads, self.unlimited)
        self.assertIn("max", why)

    def test_a_missing_file_means_no_quota(self):
        threads, why = cpu.thread_count(**self.paths())
        self.assertEqual(threads, self.unlimited)
        self.assertIn("no cgroup", why)

    def test_unparseable_content_does_not_raise(self):
        """A surprise in a kernel file must degrade, never take the pod down."""
        for junk in ("garbage", "", "100000", "a b", "100000 0", "0 100000"):
            with self.subTest(content=junk):
                threads, _ = cpu.thread_count(**self.paths(v2=junk))
                self.assertEqual(threads, self.unlimited)

    def test_the_setting_overrides_everything(self):
        settings.torch_threads = 7
        threads, why = cpu.thread_count(**self.paths(v2="100000 100000"))
        self.assertEqual(threads, 7)
        self.assertEqual(why, "BA_TORCH_THREADS")

    def test_cgroup_v1_is_read_when_v2_is_absent(self):
        threads, why = cpu.thread_count(**self.paths(quota="200000", period="100000"))
        self.assertEqual(threads, 2)
        self.assertIn("cfs_quota_us", why)

    def test_cgroup_v1_minus_one_means_unlimited(self):
        threads, _ = cpu.thread_count(**self.paths(quota="-1", period="100000"))
        self.assertEqual(threads, self.unlimited)

    def test_v2_wins_over_v1_when_both_exist(self):
        places = self.paths(v2="400000 100000", quota="100000", period="100000")
        self.assertEqual(cpu.thread_count(**places)[0], 4)


class QuotaReadingTest(unittest.TestCase):
    """`cpu_quota` reports cores and its own source, so the log line can too."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def test_it_reports_the_cores_and_the_file_it_read(self):
        path = self.dir / "cpu.max"
        path.write_text("150000 100000")
        cores, source = cpu.cpu_quota(v2=path, v1_quota=self.dir / "x", v1_period=self.dir / "y")
        self.assertAlmostEqual(cores, 1.5)
        self.assertIn(str(path), source)

    def test_a_fractional_quota_floors_but_never_below_two(self):
        """1.5 cores floors to 1, and the floor of two then applies."""
        path = self.dir / "cpu.max"
        path.write_text("150000 100000")
        threads, _ = cpu.thread_count(v2=path, v1_quota=self.dir / "x", v1_period=self.dir / "y")
        self.assertEqual(threads, 2)


class ThreadEnvTest(unittest.TestCase):
    """`set_thread_env` is the half that actually changes anything.

    Measured at a one-core quota: telling torch alone, after it was imported,
    was *slower* than leaving it untouched - 191.23s a search against 165.95s -
    because the OpenMP pool underneath had already been built with ten threads.
    The environment variables are what that pool reads, and only before it is
    built. Nothing here imports torch; the suite stays offline and fast.
    """

    NAMES = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")

    def setUp(self):
        for name in self.NAMES:
            self.addCleanup(self._restore, name, os.environ.get(name))
            os.environ.pop(name, None)
        self.addCleanup(setattr, settings, "torch_threads", settings.torch_threads)

    @staticmethod
    def _restore(name, value):
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def test_it_publishes_the_count_into_every_pool_variable(self):
        settings.torch_threads = 3
        threads, why = cpu.set_thread_env()
        self.assertEqual(threads, 3)
        self.assertEqual(why, "BA_TORCH_THREADS")
        for name in self.NAMES:
            self.assertEqual(os.environ[name], "3", name)

    def test_a_value_set_by_hand_outranks_us(self):
        """An operator who set it deliberately is not second-guessed."""
        os.environ["OMP_NUM_THREADS"] = "6"
        settings.torch_threads = 3
        cpu.set_thread_env()
        self.assertEqual(os.environ["OMP_NUM_THREADS"], "6")
        self.assertEqual(os.environ["MKL_NUM_THREADS"], "3")


if __name__ == "__main__":
    unittest.main()
