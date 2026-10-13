#!/bin/sh
# Audit the federalism study's conclusions with ai-auditor.
# Needs ANTHROPIC_API_KEY in the environment (or an `ant auth login` profile).
# Makes billed API calls: roughly 7 model calls, one with web search.
set -e
cd "$(dirname "$0")/.."
~/ai-auditor/.venv/bin/ai-auditor \
  "In Canada, which level of government should control transit, environmental protection, redistribution and schools, and how much should we trust a calibrated simulation-based answer to that question?" \
  --solution @audit/claims.md \
  --plugin audit/structural_gaps.py \
  --skip external_test \
  --model claude-opus-5-5 \
  --continue-on-error -v \
  --json -o audit/result-v2.json
echo "wrote audit/result-v2.json"
