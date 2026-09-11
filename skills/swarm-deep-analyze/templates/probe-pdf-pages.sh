#!/usr/bin/env bash
# Probe a PDF's per-page byte count to detect empty/missing ranges before chunking.
# Use this BEFORE assigning builders to page ranges so you don't dispatch a builder
# to a non-existent range (FORGE swarm hit this — page 21–27 of a 19-page PDF).
#
# Usage: ./probe-pdf-pages.sh path/to/file.pdf [max_page_to_probe]
# Output: TSV — page, bytes, exists(yes/no)
set -euo pipefail

PDF="${1:?Usage: probe-pdf-pages.sh path/to/file.pdf [max_page]}"
MAX="${2:-50}"

if [[ ! -f "$PDF" ]]; then
  echo "ERROR: $PDF not found" >&2
  exit 1
fi

if ! command -v pdftotext &>/dev/null; then
  echo "ERROR: pdftotext not installed. Install Poppler or use python -m pdfminer.high_level." >&2
  exit 1
fi

printf "page\tbytes\texists\n"

for ((p=1; p<=MAX; p++)); do
  bytes=$(pdftotext -layout -f "$p" -l "$p" "$PDF" - 2>/dev/null | wc -c | tr -d ' ')
  if [[ "$bytes" -gt 50 ]]; then
    printf "%d\t%d\tyes\n" "$p" "$bytes"
  else
    printf "%d\t%d\tno\n" "$p" "$bytes"
    # If we've hit 2 consecutive empty pages, stop probing
    if [[ "${prev_empty:-0}" == "1" ]]; then
      echo "# Two consecutive empty pages — PDF ends before page $p" >&2
      break
    fi
    prev_empty=1
    continue
  fi
  prev_empty=0
done
