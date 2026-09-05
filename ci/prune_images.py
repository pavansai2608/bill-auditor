"""Decide which bill-auditor images a finished main build may delete.

WHY THIS IS A MODULE AND NOT A SHELL LOOP

Every build produces a full set of five images - about 8.5GB of repositories,
though far less on disk because the tags share layers. Left alone that is one
more set per build. The deletion itself is two commands; the decision about
*which* tags may go is the part worth testing, so it lives here as a pure
function and the stage only calls it.

THE FOURTH KEEP RULE IS THE ONE THAT MATTERS

Keeping N, N-1 and latest is obvious. The rule that is not obvious is the
fourth: a tag referenced by a live Kubernetes deployment survives whatever its
number. That exists because the cluster does not necessarily run what the build
just pushed. Before `k8s/deploy.sh` existed, `kubectl apply` started no rollout
at all - the manifests pin `:latest`, so the Deployment spec never changed - and
the pods went on running an image loaded by hand days earlier while the stage
reported success. On 2026-09-05 the pods were two days old and build 22, an hour
finished, had never reached them.

Pruning on the arithmetic alone would have deleted the image the cluster was
actually serving. So the live references are read from the cluster at prune
time, and they outrank the numbers.

NOTHING OUTSIDE bill-auditor/ IS EVER A CANDIDATE

The delete list is filtered to repositories under `bill-auditor/` before any
other rule runs. This machine also holds ollama, python, node, nginx, kind and
minikube base images and two other projects' images. A tag number colliding
with one of ours is not a reason to touch it - `traffic-app:v1` and
`bill-auditor/gateway:22` have nothing to do with each other.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Iterable, Sequence

#: Only repositories under this prefix may ever be deleted.
OURS = "bill-auditor/"

#: Registry prefixes that name the same image. `kubectl` reports
#: `bill-auditor/gateway:25` while `minikube image ls` reports
#: `docker.io/bill-auditor/gateway:25`, and they are the same thing.
REGISTRY_PREFIXES = (
    "docker.io/library/",
    "docker.io/",
    "index.docker.io/library/",
    "index.docker.io/",
    "registry.hub.docker.com/",
)

KEEP_LATEST = "latest"


def normalise(ref: str) -> str:
    """Strip the registry host so refs from different tools compare equal."""
    ref = ref.strip()
    for prefix in REGISTRY_PREFIXES:
        if ref.startswith(prefix):
            return ref[len(prefix) :]
    return ref


def is_ours(ref: str) -> bool:
    """True only for repositories under `bill-auditor/`."""
    return normalise(ref).startswith(OURS)


def tag_of(ref: str) -> str:
    """The tag part of `repo:tag`, or "" when there is none.

    Splits on the last colon after the last slash, so a registry with a port
    (`localhost:5000/x`) does not read as a tag.
    """
    name = normalise(ref)
    _, slash, remainder = name.rpartition("/")
    if slash and ":" in remainder:
        return remainder.rsplit(":", 1)[1]
    if not slash and ":" in name:
        return name.rsplit(":", 1)[1]
    return ""


def partition(
    images: Sequence[str],
    build_number: int | None,
    live: Iterable[str] = (),
) -> tuple[list[str], list[str]]:
    """Split `images` into (keep, delete).

    A reference is kept when any of these holds:

    1. it is not ours - anything outside `bill-auditor/` is never a candidate
    2. its tag is the current build number
    3. its tag is the current build number minus one
    4. its tag is `latest`
    5. it is referenced by a live Kubernetes deployment, whatever its number

    Rule 5 outranks the arithmetic: an image the cluster is serving survives
    even when it is far older than N-1.

    `keep` and `delete` are disjoint and together cover `images`, in input
    order.

    `build_number` may be None, and then **nothing of ours is nominated for
    deletion**. A pruner that cannot tell which build it is cannot tell N from
    N-1, and the arithmetic that protects the current build is exactly what it
    has lost. The earlier behaviour - protect only `latest` and the live refs -
    made an unknown N delete *more* than a known one: with no number, tags 25
    and 24 both became candidates. Deleting the build that just deployed is the
    worst outcome this module can produce, so an unknown N is fail-safe here as
    well as in `main`, and the guarantee does not rest on one caller remembering
    to check.
    """
    live_refs = {normalise(ref) for ref in live if ref and ref.strip()}

    if build_number is None:
        return [ref for ref in images if ref and ref.strip()], []

    kept_numbers: set[str] = {str(build_number)}
    if build_number - 1 >= 0:
        kept_numbers.add(str(build_number - 1))

    keep: list[str] = []
    delete: list[str] = []

    for ref in images:
        if not ref or not ref.strip():
            continue
        if not is_ours(ref):
            keep.append(ref)
            continue
        if normalise(ref) in live_refs:
            keep.append(ref)
            continue
        tag = tag_of(ref)
        if tag == KEEP_LATEST or tag in kept_numbers:
            keep.append(ref)
            continue
        delete.append(ref)

    return keep, delete


def why_kept(ref: str, build_number: int | None, live_refs: set[str]) -> str:
    """A short reason, for the log. The operator should not have to infer it."""
    if not is_ours(ref):
        return "not a bill-auditor image"
    if normalise(ref) in live_refs:
        return "live in the cluster"
    tag = tag_of(ref)
    if tag == KEEP_LATEST:
        return "latest"
    if build_number is not None and tag == str(build_number):
        return f"current build ({build_number})"
    if build_number is not None and tag == str(build_number - 1):
        return f"previous build ({build_number - 1})"
    return "kept"


# --------------------------------------------------------------------------
# Reading the real world. Nothing below is imported by the tests.
# --------------------------------------------------------------------------


def _run(args: list[str]) -> tuple[int, str]:
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover
        return 1, str(exc)
    return done.returncode, done.stdout


def docker_images() -> list[str]:
    """Every `repo:tag` in Docker Desktop's daemon."""
    code, out = _run(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"])
    if code != 0:
        return []
    return [line for line in out.splitlines() if line.strip() and "<none>" not in line]


def minikube_profile() -> str | None:
    """The active minikube profile, resolved rather than assumed.

    `minikube profile` prints the name decorated for a terminal, so the JSON
    listing is used instead and the profile marked active is taken.
    """
    code, out = _run(["minikube", "profile", "list", "-o", "json"])
    if code != 0:
        return None
    try:
        data = json.loads(out)
    except ValueError:
        return None
    for group in ("valid", "invalid"):
        for profile in data.get(group) or []:
            if profile.get("ActiveProfile") or profile.get("Active"):
                return profile.get("Name")
    valid = data.get("valid") or []
    return valid[0].get("Name") if valid else None


def minikube_images(profile: str) -> list[str]:
    """Every `repo:tag` in minikube's own daemon, which is not Docker Desktop's."""
    code, out = _run(["minikube", "-p", profile, "image", "ls"])
    if code != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip() and "<none>" not in line]


def cluster_images() -> list[str] | None:
    """The image field of every container of every live deployment.

    Every namespace, not just bill-auditor. An image this build did not push
    but something is running is still an image nothing may delete.

    Returns None when the cluster could not be read, and `[]` only when it was
    read and genuinely holds nothing. The two used to be the same value, which
    quietly disabled rule 5: `kubectl` exits non-zero on connection refused, so
    a stopped minikube reported "no live images" and the pruner went on to
    delete on the arithmetic alone - against an unreachable cluster that may
    well still have pods running an older tag. An unreachable cluster is not
    evidence that nothing is running.
    """
    code, out = _run(
        [
            "kubectl",
            "get",
            "deploy",
            "-A",
            "-o",
            "jsonpath={range .items[*]}{range .spec.template.spec.containers[*]}"
            '{.image}{"\\n"}{end}{end}',
        ]
    )
    if code != 0:
        return None
    return [line.strip() for line in out.splitlines() if line.strip()]


def _report(
    daemon: str,
    images: list[str],
    keep: list[str],
    delete: list[str],
    build_number: int | None,
    live_refs: set[str],
) -> None:
    print(f"\n=== {daemon}: {len(images)} image(s), keep {len(keep)}, delete {len(delete)}")
    ours = [r for r in keep if is_ours(r)]
    others = len(keep) - len(ours)
    print("  KEEP:")
    for ref in sorted(ours):
        print(f"    {ref:52} {why_kept(ref, build_number, live_refs)}")
    if others:
        print(f"    ({others} non bill-auditor image(s), never candidates)")
    print("  DELETE:")
    if not delete:
        print("    (nothing)")
    for ref in sorted(delete):
        print(f"    {ref}")


def _delete(daemon: str, refs: list[str], profile: str | None) -> int:
    failures = 0
    for ref in refs:
        if daemon == "docker":
            code, _ = _run(["docker", "rmi", ref])
        else:
            code, _ = _run(["minikube", "-p", profile or "minikube", "image", "rm", ref])
        status = "removed" if code == 0 else "FAILED"
        print(f"    {status}: {ref}")
        failures += 0 if code == 0 else 1
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--build-number",
        type=int,
        default=None,
        help="the current build number, N. Without it only latest "
        "and the live cluster references are protected.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print the partition and delete nothing"
    )
    args = parser.parse_args(argv)

    # An unknown N is refused before anything is read. The number is what
    # separates the build that just deployed from the ones that did not, and a
    # pruner that has to guess which build it is must not guess.
    if args.build_number is None:
        print("REFUSING TO PRUNE: no build number.")
        print("    Pass --build-number N. Without it this run cannot tell the")
        print("    current build from an old one, and the tag it would delete")
        print("    first is the one that just deployed.")
        return 2

    live = cluster_images()

    if live is None:
        print("REFUSING TO PRUNE: the cluster could not be read.")
        print("    kubectl exited non-zero - no cluster, wrong context, or the")
        print("    API server is down. That is not evidence that nothing is")
        print("    running; pods may still be serving a tag older than N-1.")
        print("    Everything is kept. Fix the cluster, or the next green build prunes.")
        return 0

    live_refs = {normalise(ref) for ref in live}
    if live:
        print("live in the cluster:")
        for ref in sorted(r for r in live if is_ours(r)):
            print(f"    {ref}")
    else:
        print("live in the cluster: read successfully, no deployments.")
        print("    Rule 5 protects nothing, so this run keeps N, N-1 and latest.")

    # Docker Desktop's daemon.
    d_images = docker_images()
    d_keep, d_delete = partition(d_images, args.build_number, live)
    _report("docker", d_images, d_keep, d_delete, args.build_number, live_refs)

    # minikube's daemon, which holds a separate store of the same names.
    profile = minikube_profile()
    if profile is None:
        print("\n=== minikube: not running or no profile - skipped, nothing deleted there.")
        m_delete: list[str] = []
    else:
        m_images = minikube_images(profile)
        m_keep, m_delete = partition(m_images, args.build_number, live)
        _report(f"minikube ({profile})", m_images, m_keep, m_delete, args.build_number, live_refs)

    if args.dry_run:
        print(f"\ndry run: {len(d_delete) + len(m_delete)} image(s) would be deleted, none were.")
        return 0

    failures = 0
    if d_delete:
        print("\ndeleting from docker:")
        failures += _delete("docker", d_delete, None)
    if m_delete:
        print("\ndeleting from minikube:")
        failures += _delete("minikube", m_delete, profile)
    if not d_delete and not m_delete:
        print("\nnothing to delete.")
    # A tag that will not delete is not a reason to fail a build that already
    # deployed: it is still referenced by something, and the next run retries.
    if failures:
        print(f"\n{failures} image(s) could not be removed; left in place.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
