# Run summary — kuairand-20260831-180915

## Results (KuaiRand-Pure)

| | GAUC | nDCG@5 | primary |
|---|---|---|---|
| official baseline (valid) | 0.6674 | 0.5357 | 0.6016 |
| official baseline (hidden test) | 0.661 | 0.5282 | 0.5946 |
| this run, validation-best | — | — | 0.5978366001474253 |

Absolute delta vs official validation baseline: **-0.0038**

## Resource usage

- LLM tokens: **182,739** (137,961 in / 44,778 out)
- Agent wall-clock: **0.873 h**
- Iterations used: **6 of 50**
- GPU-hours: **0** — CPU-only run (candidate training used 0.2605 h of CPU time)

## Autonomy & robustness

- Manual interventions during the run: **0**
- Accepted improvements (promotions): **1**
- Errors encountered: **1**, automatic recoveries: **0**
- Converged / ended cleanly: **True**

## Iterations

| # | hypothesis | mechanism | outcome | Δ | diff |
|---|---|---|---|---|---|
| 1 | — | — | no verdict | — | — |
| 2 | target-encoding | features/target-encoding | rejected | -0.0918 | patches/node-002.diff |
| 3 | pairwise | objective/pairwise | rejected | -0.0184 | patches/node-003.diff |
| 4 | dur-log-buckets | features/dur-log-buckets | promoted | +0.0022 | patches/node-004.diff |
| 5 | tab-cross | features/tab-cross | inconclusive | -0.0005 | patches/node-005.diff |
| 6 | user-activity-bucket | features/user-activity-bucket | rejected | -0.0078 | patches/node-006.diff |

Full per-iteration detail: `iterations.jsonl`.
