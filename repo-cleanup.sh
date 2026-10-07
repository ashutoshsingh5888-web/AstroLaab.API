#!/usr/bin/env bash
# One-off repo hygiene: stop tracking the committed virtualenv and bytecode.
# (1,900+ files under venv/ and several __pycache__/*.pyc were committed.)
# Files stay on disk; .gitignore (added by the hardening patch) keeps them out.
set -euo pipefail
git rm -r -q --cached venv 2>/dev/null || true
git ls-files '*.pyc' -z | xargs -0 -r git rm -q --cached
git status --short | head -5
echo "Now commit: git commit -m 'chore: stop tracking venv and bytecode'"
