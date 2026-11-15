#!/bin/zsh
set -eu
cd "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  echo "Create the Python environment using the README setup instructions first."
  exit 1
fi
exec .venv/bin/python -m stormwater.server --port 8765
