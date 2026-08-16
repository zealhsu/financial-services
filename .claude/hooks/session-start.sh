#!/bin/bash
set -euo pipefail

# Claude Code on the web hands each session a fresh container, so plugins
# installed by hand are gone by the next one. Reinstall the FSI plugins this
# repo publishes, so /dcf, /comps, /earnings and /screen are there on arrival.
#
# Local sessions are left alone -- installing plugins into someone's own
# machine behind their back is not this hook's business.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

MARKETPLACE="claude-for-financial-services"
PLUGINS="financial-analysis equity-research market-researcher earnings-reviewer"
SETTINGS="$HOME/.claude/settings.json"

# Every `claude` invocation costs about a second of CLI startup, and this hook
# runs before the session does. On a warm container there is nothing to do, so
# check the recorded state directly rather than paying five CLI round-trips to
# be told everything is already installed.
mcp_cache_is_valid() {
  local found=1 cached
  for cached in "$HOME"/.claude/plugins/cache/"$MARKETPLACE"/financial-analysis/*/.mcp.json; do
    [ -f "$cached" ] || continue
    found=0
    python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$cached" 2>/dev/null || return 1
  done
  return $found
}

already_installed() {
  [ -f "$SETTINGS" ] || return 1
  local plugin
  for plugin in $PLUGINS; do
    grep -q "\"$plugin@$MARKETPLACE\"[[:space:]]*:[[:space:]]*true" "$SETTINGS" || return 1
  done
  mcp_cache_is_valid
}

if already_installed; then
  exit 0
fi

# Both are idempotent; re-adding or re-installing an existing entry is a no-op.
claude plugin marketplace add anthropics/financial-services >/dev/null 2>&1 || true
for plugin in $PLUGINS; do
  claude plugin install "$plugin@$MARKETPLACE" >/dev/null 2>&1 || true
done

# Upstream's financial-analysis .mcp.json has been malformed since the Box
# connector landed (#187) -- a missing comma and an unclosed brace. Every one
# of the 12 data connectors is silently dropped while `plugin install` still
# reports success, so the failure reads as a data-source auth problem rather
# than a syntax error. Repair the cached copy from this repo's fixed version.
# Once the fix is upstream the cached file parses and this loop does nothing.
repo_mcp="$CLAUDE_PROJECT_DIR/plugins/vertical-plugins/financial-analysis/.mcp.json"
for cached in "$HOME"/.claude/plugins/cache/"$MARKETPLACE"/financial-analysis/*/.mcp.json; do
  [ -f "$cached" ] || continue
  if python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$cached" 2>/dev/null; then
    continue
  fi
  cp "$repo_mcp" "$cached"
  echo "session-start: repaired malformed .mcp.json in $(basename "$(dirname "$cached")")"
done
