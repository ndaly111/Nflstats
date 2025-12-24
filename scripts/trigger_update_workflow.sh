#!/usr/bin/env bash
# Trigger the "Update EPA data" GitHub Actions workflow from the CLI.
# Requires GitHub CLI (`gh`) and a token with `workflow` scope (`GH_TOKEN` or
# `GITHUB_TOKEN`). Usage examples:
#
#   ./scripts/trigger_update_workflow.sh                    # update_current on default branch
#   ./scripts/trigger_update_workflow.sh backfill_season 2023
#   ./scripts/trigger_update_workflow.sh backfill_range '' 2000 2024
#
set -euo pipefail

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) is required to trigger the workflow" >&2
  exit 1
fi

mode=${1:-update_current}
season=${2:-}
season_start=${3:-}
season_end=${4:-}

args=(workflow run update-epa-data.yml)
args+=(--ref "${GITHUB_REF:-main}")
args+=(-f mode="${mode}")

if [[ -n "${season}" ]]; then
  args+=(-f season="${season}")
fi
if [[ -n "${season_start}" ]]; then
  args+=(-f season_start="${season_start}")
fi
if [[ -n "${season_end}" ]]; then
  args+=(-f season_end="${season_end}")
fi

exec gh "${args[@]}"
