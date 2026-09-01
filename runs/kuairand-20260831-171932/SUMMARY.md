# Run summary — kuairand-20260831-171932

## Results (KuaiRand-Pure)

| | GAUC | nDCG@5 | primary |
|---|---|---|---|
| official baseline (valid) | 0.6674 | 0.5357 | 0.6016 |
| official baseline (hidden test) | 0.661 | 0.5282 | 0.5946 |
| this run, validation-best | — | — | 0.598881381520826 |

Absolute delta vs official validation baseline: **-0.0027**

## Resource usage

- LLM tokens: **464,949** (355,956 in / 108,993 out)
- Agent wall-clock: **0.812 h**
- Iterations used: **6 of 50**
- GPU-hours: **0** — CPU-only run (candidate training used 0.254 h of CPU time)

## Autonomy & robustness

- Manual interventions during the run: **0**
- Accepted improvements (promotions): **0**
- Errors encountered: **8**, automatic recoveries: **0**
- Converged / ended cleanly: **True**

## Iterations

| # | hypothesis | mechanism | outcome | Δ | diff |
|---|---|---|---|---|---|
| 1 | — | — | no verdict | — | — |
| 2 | target-encoding | features/target-encoding | inconclusive | +0.0000 | patches/node-002.diff |
| 3 | pairwise | objective/pairwise | inconclusive | -0.0002 | patches/node-003-d2.diff |
| 4 | dur-log-buckets | features/dur-log-buckets | inconclusive | -0.0001 | patches/node-004-d1.diff |
| 5 | tab-cross | features/tab-cross | inconclusive | +0.0000 | patches/node-005.diff |
| 6 | user-activity-bucket | features/user-activity-bucket | rejected | -0.0056 | patches/node-006.diff |

Full per-iteration detail: `iterations.jsonl`.
