#!/bin/zsh
set -eu
cd "${0:A:h}"
GIS_PROJECT="${1:-data/gis-demo-sydney}"
if [[ ! -f "$GIS_PROJECT/case.json" ]]; then
  ./gis demo --output "$GIS_PROJECT"
fi
exec ./gis serve --workspace "$GIS_PROJECT" --port 8766
