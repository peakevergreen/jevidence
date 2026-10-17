# jevidence

Evidence collection and analysis tooling; preserve its source/data boundaries.

## Project setup and checks

- Read [README.md](README.md), [CONTRIBUTING.md](CONTRIBUTING.md) before setup or changing the project structure.
- `.github/workflows/` is authoritative for required CI, runtime pins, and deployment triggers. Match its checks for the files you change.
- Python requirement: `>=3.10` from `pyproject.toml`. Use the repository's declared environment/dependency setup.
- Use the lint/test commands and service prerequisites in the project docs and CI. Schema/model changes need the corresponding migration in the same PR.
- Existing Make targets include `make lint`, `make test`. Read their prerequisites before invoking them.

## Scope and operational boundaries

- Preserve project identity, public assets, and existing configuration. Browser-check rendered/user-facing changes; instruction-only changes do not require starting the application.

<!-- BEGIN PEAKEVERGREEN WORKSPACE RULES -->
## Shared workspace rules

<!-- Managed by local-configs/agent-rules/sync.py; keep project facts outside this block. -->

- Keep the one permanent clone at `~/workspace/jevidence`; verify the GitHub
  owner/name before using it. Preserve existing work and other owners' folders.
- Use linked task worktrees at `~/workspace-tests/<task>/jevidence` for
  implementation, installs, and tests. Record ownership, base SHA, branch, and
  state in the task's `task.json`; put generated artifacts in that task area.
- Fetch and discover the actual default branch. New tasks start there; named
  PR/release/history work keeps its intended base. Isolate ports/test databases.
  Set and verify `WORKSPACE_ROOT` before shared local-dev setup or unlink.
- Commit/push only when requested, including the necessary task commit/push for
  an explicit PR request. Preview PRs stay draft. Do not merge/deploy/publish or
  bypass hooks/signing/checks without authorization. Do not create parking stashes.
- Preserve unique local files, data, history, and every stash. Before cleanup
  inspect ignored/hidden files, HEAD/reflog/worktree refs, nested repos, locks,
  processes, and incoming editable links from all retained checkouts. Use exact
  PR-head/patch evidence for squash merges; do not infer safety from status alone.
- Once all valuable work is verified on GitHub, remove clean task worktrees with
  plain `git worktree remove` (or their creating tool); never force it. Record
  open PRs. After merge, fast-forward the clean idle permanent default checkout
  and refresh changed dependencies. Preserve dirty/diverged/active checkouts.
- Keep repository facts and checks outside this block. For instruction-only changes, validate
  the shared block, Claude import, and `git diff --check`; installed hooks and
  additional mandatory project checks still apply. Use the actual lockfile and
  runtime pins for application validation; never switch package managers.

Detailed lifecycle and recovery: [workspace policy](https://github.com/peakevergreen/local-configs/blob/059707e6c04f61710b4927da5e9132fd763638d4/docs/agent-git-workspace.md).
<!-- END PEAKEVERGREEN WORKSPACE RULES -->
