# Run summary — kuairand-20260901-021859

## Results (KuaiRand-Pure)

| | GAUC | nDCG@5 | primary |
|---|---|---|---|
| official baseline (valid) | 0.6674 | 0.5357 | 0.6016 |
| official baseline (hidden test) | 0.661 | 0.5282 | 0.5946 |
| this run, validation-best | — | — | 0.5973414809895083 |

Absolute delta vs official validation baseline: **-0.0043**

## Resource usage

- LLM tokens: **346,090** (232,114 in / 113,976 out)
- Agent wall-clock: **0.733 h**
- Iterations used: **9 of 50**
- GPU-hours: **0** — CPU-only run (candidate training used 0.1182 h of CPU time)

## Autonomy & robustness

- Manual interventions during the run: **0**
- Accepted improvements (promotions): **0**
- Errors encountered: **1**, automatic recoveries: **6**
- Converged / ended cleanly: **False**

## Iterations

| # | hypothesis | mechanism | outcome | Δ | diff |
|---|---|---|---|---|---|
| 1 | — | — | no verdict | — | — |
| 2 | video-popularity-bucket | features/video-popularity-bucket | inconclusive | +0.0000 | patches/node-002.diff |
| 3 | lgbm-trees | architecture/lgbm-trees | rejected | -0.0062 | patches/node-003.diff |
| 4 | deep-cross | architecture/deep-cross | rejected | -0.0149 | patches/node-004.diff |
| 5 | pairwise-grouped | objective/pairwise-grouped | inconclusive | +0.0001 | patches/node-005.diff |
| 6 | dur-log-buckets | features/dur-log-buckets | inconclusive | -0.0002 | patches/node-006.diff |
| 7 | tab-cross | features/tab-cross | inconclusive | +0.0000 | patches/node-007.diff |
| 8 | author-freq-bucket | features/author-freq-bucket | inconclusive | +0.0000 | patches/node-008.diff |
| 9 | date-token | features/date-token | replicating | +0.0009 | patches/node-009.diff |

Full per-iteration detail: `iterations.jsonl`.
