# Automation scripts

Optional local helpers. Releases go through [GitHub Actions](../.github/workflows/ci.yml) (`workflow_dispatch` → `production_release`).

| Script | Purpose |
| --- | --- |
| `build-local.sh` | Build and smoke-test a Docker image locally |
| `create_release.sh` | Create a GitHub release tag |
| `test_github_access.sh` | Check `gh` auth |
| `close_pr.sh` / `comment_on_pr.sh` | PR helpers |

Run from the repo root, for example `./automations/build-local.sh`.
