#!/usr/bin/env bash
# Install the mmap skill into the Claude Code user-level skills directory.
#
#   ./install.sh          # copy the skill into ~/.claude/skills/mmap (default)
#   ./install.sh link     # symlink instead (edits in this repo go live immediately)
#   CLAUDE_SKILLS_DIR=~/.codex/skills ./install.sh   # install for another agent
#
# After installing, open Claude Code in ANY project and run:  /mmap architecture
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
DEST="$SKILLS_DIR/mmap"
MODE="${1:-copy}"

command -v python3 >/dev/null 2>&1 || {
  echo "ERROR: python3 (>=3.9) is required at render time but was not found." >&2; exit 1; }

mkdir -p "$SKILLS_DIR"
if [ -e "$DEST" ] || [ -L "$DEST" ]; then
  echo "Replacing existing $DEST"
  rm -rf "$DEST"
fi

case "$MODE" in
  link)
    ln -s "$SRC" "$DEST"
    echo "Symlinked $DEST -> $SRC  (edits in this repo are live)"
    ;;
  copy)
    mkdir -p "$DEST"
    cp -R "$SRC/SKILL.md" "$SRC/scripts" "$SRC/assets" "$SRC/references" "$DEST/"
    echo "Copied skill to $DEST"
    ;;
  *)
    echo "Usage: ./install.sh [copy|link]" >&2; exit 1 ;;
esac

# sanity check: the renderer runs and the placeholders are present
if [ -f "$DEST/scripts/render_mindmap.py" ] && [ -f "$DEST/assets/template.html" ]; then
  echo "OK: skill files in place."
else
  echo "WARNING: expected files missing under $DEST" >&2; exit 1
fi

echo
echo "Done. In any project, run:  /mmap architecture   |   /mmap decisions   |   /mmap <a flow>"
echo "(Restart Claude Code if /mmap doesn't show up immediately.)"
