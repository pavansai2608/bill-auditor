"""The keep/delete decision, which is the only part of pruning worth testing.

Deleting is two commands. Choosing what may be deleted is where a mistake costs
either disk that never comes back or, far worse, the image the cluster is
currently serving.
"""

import contextlib
import io
import unittest

from ci import prune_images
from ci.prune_images import is_ours, normalise, partition, tag_of

BUILD = 25

STORE = [
    "bill-auditor/gateway:25",
    "bill-auditor/gateway:24",
    "bill-auditor/gateway:19",
    "bill-auditor/gateway:latest",
    "ollama/ollama:latest",
]


def refs(*tags: str, service: str = "gateway") -> list[str]:
    return [f"bill-auditor/{service}:{tag}" for tag in tags]


def _main_with(cluster, argv):
    """Run `main` against a stubbed world and return (stdout, exit code).

    Only the readers are stubbed - the decision and the reporting are the real
    ones, so these tests exercise the code the Jenkins stage actually calls.
    Always passes --dry-run; nothing here may delete.
    """
    saved = (prune_images.cluster_images, prune_images.docker_images, prune_images.minikube_profile)
    prune_images.cluster_images = lambda: cluster
    prune_images.docker_images = lambda: list(STORE)
    prune_images.minikube_profile = lambda: None
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            code = prune_images.main(argv)
    finally:
        (prune_images.cluster_images, prune_images.docker_images, prune_images.minikube_profile) = (
            saved
        )
    return buffer.getvalue(), code


class TagParsingTest(unittest.TestCase):
    def test_registry_prefix_is_stripped(self):
        # kubectl says bill-auditor/gateway:25, minikube says
        # docker.io/bill-auditor/gateway:25. They are the same image.
        self.assertEqual(normalise("docker.io/bill-auditor/gateway:25"), "bill-auditor/gateway:25")
        self.assertEqual(normalise("bill-auditor/gateway:25"), "bill-auditor/gateway:25")

    def test_a_registry_port_is_not_read_as_a_tag(self):
        self.assertEqual(tag_of("localhost:5000/bill-auditor/gateway:25"), "25")
        self.assertEqual(tag_of("localhost:5000/bill-auditor/gateway"), "")

    def test_only_bill_auditor_is_ours(self):
        self.assertTrue(is_ours("bill-auditor/gateway:25"))
        self.assertTrue(is_ours("docker.io/bill-auditor/gateway:25"))
        self.assertFalse(is_ours("bill-auditor-gateway:latest"))  # the compose name
        self.assertFalse(is_ours("ollama/ollama:latest"))


class WhatIsKeptTest(unittest.TestCase):
    def test_current_build_previous_build_and_latest_are_kept(self):
        images = refs("25", "24", "latest", "23", "22")
        keep, delete = partition(images, BUILD)
        self.assertEqual(
            sorted(keep),
            sorted(refs("25", "24", "latest")),
        )
        self.assertEqual(sorted(delete), sorted(refs("23", "22")))

    def test_an_image_live_in_the_cluster_is_kept_however_old(self):
        # The case this rule exists for. Before k8s/deploy.sh, `kubectl apply`
        # started no rollout - the manifests pin :latest so the spec never
        # changed - and the pods went on running a much older tag while the
        # stage reported success. Pruning on the arithmetic alone would have
        # deleted the image the cluster was actually serving.
        images = refs("25", "24", "latest", "7")
        keep, delete = partition(images, BUILD, live=["bill-auditor/gateway:7"])
        self.assertIn("bill-auditor/gateway:7", keep)
        self.assertEqual(delete, [])

    def test_the_live_reference_is_matched_across_registry_spellings(self):
        images = refs("11")
        keep, delete = partition(images, BUILD, live=["docker.io/bill-auditor/gateway:11"])
        self.assertEqual(keep, refs("11"))
        self.assertEqual(delete, [])

    def test_live_protects_only_that_repository(self):
        # gateway:11 being live says nothing about frontend:11.
        images = refs("11") + refs("11", service="frontend")
        keep, delete = partition(images, BUILD, live=["bill-auditor/gateway:11"])
        self.assertEqual(keep, ["bill-auditor/gateway:11"])
        self.assertEqual(delete, ["bill-auditor/frontend:11"])

    def test_build_number_one_has_no_previous_build(self):
        keep, delete = partition(refs("1", "latest"), 1)
        self.assertEqual(sorted(keep), sorted(refs("1", "latest")))
        self.assertEqual(delete, [])

    def test_without_a_build_number_nothing_of_ours_is_nominated(self):
        # This replaces a test that asserted the opposite. Protecting only
        # `latest` when N is unknown made an unknown N delete MORE than a known
        # one: on a nine-image store, build 25 nominated 2 tags and no build
        # number nominated 6 - including 25 and 24, the build that had just
        # deployed and the one before it. An unknown N is now fail-safe.
        keep, delete = partition(refs("25", "24", "19", "latest"), None, live=[])
        self.assertEqual(keep, refs("25", "24", "19", "latest"))
        self.assertEqual(delete, [])


class WhatIsNeverTouchedTest(unittest.TestCase):
    def test_a_foreign_image_is_never_deleted_even_at_a_matching_tag_number(self):
        # traffic-app:22 and bill-auditor/gateway:22 have nothing to do with
        # each other. This machine also carries two other projects' images.
        images = [
            "bill-auditor/gateway:22",
            "traffic-app:22",
            "other-project/api:22",
            "ollama/ollama:latest",
            "python:3.12-slim",
            "node:20-alpine",
            "bill-auditor-gateway:latest",  # the compose image, hyphen not slash
        ]
        keep, delete = partition(images, BUILD)
        self.assertEqual(delete, ["bill-auditor/gateway:22"])
        for foreign in images[1:]:
            self.assertIn(foreign, keep)
            self.assertNotIn(foreign, delete)

    def test_the_compose_images_are_not_ours_to_delete(self):
        # `docker compose` names images <project>-<service>. They run the local
        # stack and share no repository with the Jenkins-built ones.
        images = ["bill-auditor-frontend:latest", "bill-auditor-retrieval-service:latest"]
        keep, delete = partition(images, BUILD)
        self.assertEqual(delete, [])
        self.assertEqual(keep, images)


class PartitionIsTotalTest(unittest.TestCase):
    def test_an_empty_list_returns_two_empty_lists(self):
        keep, delete = partition([], BUILD)
        self.assertEqual(keep, [])
        self.assertEqual(delete, [])

    def test_an_empty_list_with_no_build_number_does_not_raise(self):
        self.assertEqual(partition([], None), ([], []))

    def test_keep_and_delete_are_disjoint_and_cover_the_input(self):
        images = [
            "bill-auditor/gateway:25",
            "bill-auditor/gateway:24",
            "bill-auditor/gateway:23",
            "bill-auditor/frontend:latest",
            "bill-auditor/audit-service:9",
            "ollama/ollama:latest",
            "kindest/node:v1.36.1",
        ]
        keep, delete = partition(images, BUILD, live=["bill-auditor/audit-service:9"])
        self.assertEqual(set(keep) & set(delete), set())
        self.assertEqual(set(keep) | set(delete), set(images))
        self.assertEqual(len(keep) + len(delete), len(images))

    def test_blank_entries_are_dropped_rather_than_misfiled(self):
        keep, delete = partition(["", "   ", "bill-auditor/gateway:3"], BUILD)
        self.assertEqual(keep, [])
        self.assertEqual(delete, ["bill-auditor/gateway:3"])


if __name__ == "__main__":
    unittest.main()


class TheClusterIsNotTheOnlyThingHoldingTheseTest(unittest.TestCase):
    """The N / N-1 rule must stand on its own.

    Until build 25 the dry runs were all saved by rule 5 - an image live in the
    cluster is kept whatever its number - so the arithmetic had never actually
    been the thing doing the protecting. Build 24 failed at Docker and no :24
    image was ever produced, which is why N-1 in particular went unexercised.
    """

    def test_current_and_previous_survive_an_empty_cluster_on_arithmetic_alone(self):
        # Scenario (a): the cluster was read and genuinely holds nothing.
        images = refs("25", "24", "19", "latest")
        keep, delete = partition(images, 25, live=[])
        self.assertIn("bill-auditor/gateway:25", keep)
        self.assertIn("bill-auditor/gateway:24", keep)
        self.assertEqual(delete, refs("19"))

    def test_cluster_images_returns_none_when_kubectl_fails(self):
        # Scenario (b) at the reader. None when kubectl exits non-zero, [] only
        # when it was read and holds nothing. Collapsing the two is what
        # silently disabled rule 5.
        saved = prune_images._run
        try:
            prune_images._run = lambda args: (1, "connection refused")
            self.assertIsNone(prune_images.cluster_images())
            prune_images._run = lambda args: (0, "")
            self.assertEqual(prune_images.cluster_images(), [])
        finally:
            prune_images._run = saved

    def test_main_refuses_and_keeps_everything_when_the_cluster_is_unreadable(self):
        # Scenario (b), through main: nothing is deleted and the run says why.
        out, code = _main_with(cluster=None, argv=["--dry-run", "--build-number", "25"])
        self.assertEqual(code, 0)
        self.assertIn("could not be read", out)
        self.assertNotIn("DELETE", out)

    def test_main_refuses_and_exits_non_zero_without_a_build_number(self):
        # Scenario (c): a pruner that cannot tell which build it is must not
        # guess, and the build should see that it did not run.
        out, code = _main_with(cluster=[], argv=["--dry-run"])
        self.assertEqual(code, 2)
        self.assertIn("no build number", out)
        self.assertNotIn("DELETE", out)

    def test_an_empty_cluster_still_reaches_the_partition(self):
        # The counterpart to the two refusals: a readable, empty cluster is a
        # normal run and must still prune, or (b) would be indistinguishable
        # from "pruning never happens".
        out, code = _main_with(cluster=[], argv=["--dry-run", "--build-number", "25"])
        self.assertEqual(code, 0)
        self.assertIn("read successfully", out)
        self.assertIn("DELETE", out)
