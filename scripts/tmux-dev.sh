#!/usr/bin/env bash
# Open (or reattach to) the TBC² tmux workspace:
#
#   +----------------------+----------------------+
#   |                      |  dev servers         |
#   |  Claude Code         |  ([api] + [web] logs)|
#   |                      +----------------------+
#   |                      |  lazygit             |
#   +----------------------+----------------------+
#
# Usage (in WSL, from anywhere):  ./scripts/tmux-dev.sh
# With other ports:               API_PORT=8100 WEB_PORT=3100 ./scripts/tmux-dev.sh
# Colours, mouse support etc. come from your own ~/.tmux.conf.

set -euo pipefail

SESSION="TBC2"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Run a program in a pane if it is installed; otherwise leave a hint there.
run_or_hint() {
  local pane="$1" cmd="$2" tool="$3"
  if command -v "$tool" >/dev/null; then
    tmux send-keys -t "$pane" "$cmd" C-m
  else
    tmux send-keys -t "$pane" "echo '$tool is not installed (see README.md)'" C-m
  fi
}

# Build the layout only if the session doesn't exist yet.
if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  # -P -F '#{pane_id}' prints each new pane's id, so we don't depend on
  # pane numbering (your config starts it at 1, tmux's default is 0).
  left=$(tmux new-session -d -s "$SESSION" -n dev -c "$ROOT" -P -F '#{pane_id}')
  top_right=$(tmux split-window -h -t "$left" -c "$ROOT" -P -F '#{pane_id}')
  bottom_right=$(tmux split-window -v -t "$top_right" -c "$ROOT" -P -F '#{pane_id}')

  run_or_hint "$left" "claude" claude
  # Pass through custom ports if you set them, e.g. API_PORT=8100 WEB_PORT=3100.
  tmux send-keys -t "$top_right" \
    "API_PORT=${API_PORT:-8000} WEB_PORT=${WEB_PORT:-3000} ./scripts/dev.sh" C-m
  run_or_hint "$bottom_right" "lazygit" lazygit

  tmux select-pane -t "$left"
fi

# Inside tmux already? Switch to the session; otherwise attach to it.
if [ -n "${TMUX:-}" ]; then
  tmux switch-client -t "$SESSION"
else
  tmux attach-session -t "$SESSION"
fi
