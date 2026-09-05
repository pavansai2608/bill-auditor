# GIT_FIX.md — put the tickets back and drop the stray fixup

Run these blocks in order, from the repository root. **Nothing here opens an
editor.** Every step that git would normally make interactive is driven by an
environment variable that answers for you.

If you ever do land in vim anyway: press `Esc`, then type `:q!` and press
`Enter`. That quits without saving, which aborts the step safely.

## What this fixes

1. No commit carries a `[BA-XX]` ticket. Two separate reasons, both true:
   `core.hooksPath` was never set, so `.githooks/` never ran at all; and the
   hook had no ticket check in it even if it had run. Both are fixed below.
2. `f2c0b1f` is still a `fixup!` commit, because the planned autosquash
   rebase was never run. (It was to live in a `GIT_COMMANDS.md`; that file was
   never created.)

---

## 0. Answer git's editors up front

Paste this once, in the same terminal you will run everything else in. It stops
any rebase or amend from opening vim.

```bash
export GIT_EDITOR=true
export GIT_SEQUENCE_EDITOR=true
export FILTER_BRANCH_SQUELCH_WARNING=1
```

## 1. Commit what is currently uncommitted

`filter-branch` refuses to run on a dirty tree, and the hook fix and its tests
are sitting uncommitted right now. These go in without tickets — the rewrite in
step 5 adds them along with everything else.

```bash
git checkout develop
git add .githooks/commit-msg tests/test_hooks.py GIT_FIX.md DECISIONS.md CLAUDE.md
git commit -m "fix(hooks): require a ticket in every commit message"
```

```bash
git status --short
```

Expect no output. If anything is still listed, add and commit it before going
on.

## 2. Back everything up

One file containing every branch and tag as they are now. If any step below
goes wrong, step 9 restores from it.

```bash
git bundle create ../bill-auditor-before-rewrite.bundle --all
git branch backup/pre-ticket-rewrite develop
git --no-pager log --oneline -1 backup/pre-ticket-rewrite
```

## 3. Confirm the fixup is empty

The rewrite drops `fixup!` commits rather than squashing them, which is only
equivalent if the fixup changed nothing.

```bash
git --no-pager show --stat f2c0b1f | tail -5
```

Expect no file names — just the commit header. **If it does list files, stop**
and use the alternative in step 8 instead of step 5.

## 4. Write the message filter

This is what adds the tickets. It skips messages that already have one, so the
old `BA-01` to `BA-08` commits keep their numbers, and it leaves `fixup!`
messages alone because step 5 drops those commits entirely.

```bash
mkdir -p /tmp/ba-fix
cat > /tmp/ba-fix/add-ticket.sh <<'EOF'
#!/bin/sh
# Reads a commit message on stdin, writes it back with [BA-NN] appended to the
# subject. The counter lives in a file because this runs once per commit, in a
# fresh subshell each time.
MSG=$(cat)
SUBJECT=$(printf '%s' "$MSG" | head -n 1)
BODY=$(printf '%s' "$MSG" | tail -n +2)

case "$SUBJECT" in
    fixup!*|squash!*) printf '%s' "$MSG"; exit 0 ;;
esac

if printf '%s' "$SUBJECT" | grep -q '\[BA-[0-9][0-9]*\]'; then
    printf '%s' "$MSG"
    exit 0
fi

NEXT=$(( $(cat "$TICKET_COUNTER") + 1 ))
printf '%s' "$NEXT" > "$TICKET_COUNTER"
printf '%s [BA-%02d]\n' "$SUBJECT" "$NEXT"
printf '%s' "$BODY"
EOF
chmod +x /tmp/ba-fix/add-ticket.sh
```

Start the counter above the highest number already used, so nothing is reused:

```bash
export TICKET_COUNTER=/tmp/ba-fix/counter
git --no-pager log --all --format=%s \
  | grep -o '\[BA-[0-9]*\]' | grep -o '[0-9]*' | sort -n | tail -1 > "$TICKET_COUNTER"
[ -s "$TICKET_COUNTER" ] || echo 0 > "$TICKET_COUNTER"
echo "numbering will start at $(( $(cat $TICKET_COUNTER) + 1 ))"
```

## 5. Rewrite every branch and tag

One pass over the whole history. It appends the tickets, drops the `fixup!`
commit, keeps the merge structure intact, and re-points the tags at the
rewritten commits.

```bash
git filter-branch -f \
  --msg-filter '/tmp/ba-fix/add-ticket.sh' \
  --commit-filter '
      case "$(git log -1 --format=%s "$GIT_COMMIT")" in
          fixup!*|squash!*) skip_commit "$@" ;;
          *) git commit-tree "$@" ;;
      esac
  ' \
  --tag-name-filter cat \
  -- --all
```

This prints one line per commit and takes a minute or two. It is not
interactive.

## 6. Check it worked

**Use `--branches --tags`, not `--all`.** `--all` means every ref under
`refs/`, which includes `refs/remotes/origin/*` - the un-rewritten copies still
sitting on GitHub. `filter-branch` cannot rewrite those and `gc` cannot drop
them; only the force-push in step 9 replaces them. Checking with `--all` before
that push reports the old history as a failure when nothing is wrong.

```bash
# Commits with no ticket, in the local history. Must print 0.
git --no-pager log --branches --tags --format=%s | grep -cv '\[BA-[0-9]'
```

```bash
# fixup commits left. Must print 0.
git --no-pager log --branches --tags --oneline | grep -c 'fixup!'
```

`grep -c` exits 1 when it counts 0, so a bare `0` with no other output is the
pass.

```bash
# The shape of the history: merges still there, tickets on everything.
git --no-pager log --oneline --graph --all | head -40
git --no-pager tag -l
```

```bash
# Tags must point at real commits in the new history, not orphans.
for t in $(git tag -l); do printf '%-8s %s\n' "$t" "$(git --no-pager log -1 --format='%h %s' "$t")"; done
```

If any of those looks wrong, go to step 9 before pushing anything.

## 7. Drop the rewrite's backup refs

`filter-branch` keeps the old history under `refs/original/`, which makes the
next `git log --all` confusing.

```bash
git for-each-ref --format='%(refname)' refs/original/ | xargs -n 1 git update-ref -d
git reflog expire --expire=now --all
git gc --prune=now --quiet
```

## 8. Alternative, only if step 3 showed the fixup was not empty

Skip this if step 3 was clean. This squashes rather than drops, and still opens
no editor because of the exports in step 0.

```bash
git rebase -i --autosquash --rebase-merges 38d2255
```

If it stops on a conflict: `git status` shows the file, fix it, then
`git add <file> && git rebase --continue`. To abandon: `git rebase --abort`.

## 9. Force-push

Your history is rewritten, so the remote has to be overwritten. You are the
only user of this repo, which is what makes that safe.

`--force-with-lease` refuses here: it compares against the remote-tracking ref,
which still holds the pre-rewrite commit, and the rewrite means the new history
is not a descendant of it. That is exactly the case this rewrite intends, so
these use `--force`. You are the only user of the repo, which is what makes
that safe.

```bash
git push --force origin develop
git push --force origin main
git push --force origin --tags
```

Four feature branches were also pushed before the rewrite and still carry the
old, ticketless history on the remote:

```bash
git push --force origin feature/answer-key feature/eval-set \
  feature/limits-and-table-lock feature/naive-audit
```

Now every ref matches, so the `--all` form finally agrees too:

```bash
git --no-pager log --all --format=%s | grep -cv '\[BA-[0-9]'
git --no-pager log --all --oneline | grep -c 'fixup!'
```

Both must print `0`. If they still do not, a stale remote-tracking ref is
left over - `git remote prune origin` clears branches deleted on GitHub.

## 10. Install the hook, so this cannot happen again

This is the step that was never run. Without it `.githooks/` is inert.

```bash
git config core.hooksPath .githooks
git config --get core.hooksPath
```

Expect `.githooks`. Then prove it blocks a bad message:

```bash
git commit --allow-empty -m "chore: this should be rejected"
```

Expect `commit-msg: BLOCKED - no [BA-XX] ticket at the end of the subject.` and
no commit created. Then the same message with a ticket:

```bash
git commit --allow-empty -m "chore(hooks): confirm the ticket check runs [BA-99]"
git reset --hard HEAD~1
```

The second one should succeed, and the reset removes it.

```bash
uv run python -m unittest tests.test_hooks
```

Expect `Ran 16 tests ... OK`. `TicketTest.test_a_message_with_no_ticket_is_rejected`
is the one that guards this specific failure.

## 11. If something went wrong

The bundle from step 2 holds everything as it was.

```bash
git checkout backup/pre-ticket-rewrite
git branch -f develop backup/pre-ticket-rewrite
git checkout develop
```

Or, from the bundle, into a fresh clone:

```bash
git clone ../bill-auditor-before-rewrite.bundle ../bill-auditor-restored
```

Once you are happy with the rewrite, remove the safety net:

```bash
git branch -D backup/pre-ticket-rewrite
rm ../bill-auditor-before-rewrite.bundle
```
