# Brief v2 — KuaiRand replaces Ali-CCP

Source: TikTok TechJam 2026 Track 2 problem statement, last updated
27 Aug 2026 5:55pm; read 29 Aug 2026. Webinar 28 Aug, recording:
https://bytedance.my.larkoffice.com/minutes/obmyo2w9q75z924p7k38bv9g

This supersedes every part of the repo that names Ali-CCP, NISE, CTR/CVR AUC,
GPU budgets, or sigma = 0.015.

## The swap

| | Old (what this repo assumes) | New (actual brief) |
|---|---|---|
| Benchmark | Ali-CCP | KuaiRand-Pure |
| Domain | Taobao e-commerce funnel | Short-video feed (Kuaishou) |
| Baseline | NISE (external repo) | Factorization Machine, k=16, lr=0.001, 5 categorical fields, numpy only, shipped in the starter kit, ~40s on one CPU core |
| Metrics | CTR AUC + CVR AUC | GAUC + nDCG@5; primary = mean of the two |
| Positive label | click, then conversion | long_view (native column) |
| Task form | binary CTR/CVR prediction | rank within each user's logged impressions (not full-catalog retrieval) |
| Scale | ~80M rows, ~38GB | 1,141,112 train rows; 1.4M interactions, 27K users x 7.6K items |
| Splits | our own carve-out | given, date-based: train 20220408-0421, val 20220422-0428 (124,909), test 20220429-0508 (170,588) |
| Compute | GPU, ~3h per run | no GPU; 50 iterations hard cap per run + 6h wall-clock backstop |
| epsilon / N | TBD | epsilon = 0.002, N = 3 (given) |
| Baseline noise | +/-0.013-0.017 (estimate) | std 0.0008 over 5 seeds (published) |
| Bonus | KuaiRand, different metrics, skipped | KuaiRand-1k / 27k, same task, same metrics |
| Feasibility scored on | GPU-hours + tokens | agent wall-clock + tokens, three coarse tiers, only among submissions that beat baseline |

Judging weights unchanged: 35 / 20 / 20 / 15 / 10. Scoring formula unchanged:
delta(m) = agent - baseline; dataset score = mean over metrics of delta.
Converged result is scored, not the peak.

## Published numbers (the new zero point)

- Baseline hidden test: GAUC 0.6610 / nDCG@5 0.5282 / primary 0.5946 (mean of 5 seeds, std 0.0008)
- Baseline validation: GAUC 0.6674 / nDCG@5 0.5357 / primary 0.6016
- Reference rungs for harness self-check: random primary 0.4753; item popularity primary 0.5715
- Attainable ceiling: primary 0.8645 (GAUC 1.0000 / nDCG@5 0.7289). 27.1% of test users have no positive, 9.2% are all-positive. Judge progress against 0.8645, not 1.0.

## Starter kit (kuairand-starter-kit.zip, 15.48 KB, linked in the brief)

- numpy only. No torch, pandas or scikit-learn.
- `python3 baseline.py --model fm` reproduces the official baseline in ~40s
- `evaluate.py` is the exact scoring code, model-agnostic, takes (user_ids, labels, scores)
- Pinned conventions: users with zero positives count as nDCG = 0 and are included in the average; GAUC counts only users with 0 < positives < impressions, weighted by positive count; nDCG gain = 2^rel - 1
- `submit.py --make` generates an example submission, `--check` validates it
- Submission schema: CSV, header `row_id,user_id,video_id,score`, one row per evaluation-split row. row_id is 0-based strictly increasing into the split as produced by data.load(). user_id/video_id are redundant alignment checks. score is any real number, order only; NaN/Inf rejected. (user_id, video_id) is NOT unique — 3.06% of test rows are repeated pairs, up to 12x — which is why row_id exists.

## What this breaks in this repo

1. Step 8 as written (Ali-CCP ingest) is dead work. No 38GB parse, no parquet partitioning, no \x01/\x02/\x03 feature-string decoding, no common-feature join, no polars streaming. 1.1M rows is a numpy array. Affected stubs: data/schema.py, data/ingest.py, data/subsample.py, harness/tasks/aliccp.py.
2. The subsample screening rung loses most of its point. It existed because a full run cost 3 GPU-hours; a full run now costs 40s.
3. The "signal smaller than noise" premise is inverted. Baseline std is 0.0008 and headroom to the ceiling is ~0.27 primary. Three-seed paired replication costs ~2 minutes, not 9 GPU-hours.
4. Every threshold in harness-decisions.md section 6 is wrong (sigma = 0.015 table, +1 sigma screen bar, mean delta >= 0.010, eta = 0.005) — all derived from Ali-CCP CVR noise. Recompute against std ~= 0.0008.
5. GPU routing, SSHBackend, CUDA_VISIBLE_DEVICES, OOM-halves-batch recovery, derived 3-hour timeouts: solving a problem we no longer have. Keep the failure-class machinery (still judged under Robustness), drop the GPU story.
6. Cost ledger changes shape. Scored numbers are total tokens (in+out), agent wall-clock, and iterations used out of 50.
7. The bonus decision inverts. KuaiRand-1k/27k are the same task, same metrics, same code path, only bigger (11.7M / 322M interactions).
8. protocols/aliccp.yaml -> protocols/kuairand_pure.yaml. The blanks we were waiting on are filled: epsilon, N, baseline published scores, submission schema, evaluation script. The split is given rather than carved.
9. "Which head is scored" is resolved and replaced. No ESMM p(click)*p(cvr|click) trap. The new equivalent trap is per-user grouping: GAUC/nDCG are computed within user over logged impressions, so a globally-calibrated score that ranks badly within users scores nothing.

## What survives unchanged

Event log, one JSONL per run, projections over it. Tree + hypothesis queue,
reranking on evidence, family = pipeline stage. Researcher/coder/tuner split;
structured hypotheses with expected gain. Synthetic benchmark with planted
effects. Judging weights, scoring formula, converged-not-peak, hidden test
scored once. Deliverables list. No external training data — the one hard rule.

## Open questions

1. Brief contradicts itself: the Constraints & Scope "Limits" row says "KuaiRand-Pure: NDCG@10 / Recall@50, click = positive (fixed)". Everything else — benchmark table, starter kit, evaluate.py, deliverables, judging — says GAUC / nDCG@5, long_view positive. Treat the Limits row as stale and trust evaluate.py. Confirm from the webinar recording.
2. Does one seed-replication run count as an "iteration"? The 50-iteration cap is now the binding constraint. Check the starter kit's loop code and the webinar.
3. Convergence counter reads the validation primary score, i.e. mean(GAUC, nDCG@5), not per-metric.
4. Older docs in this repo assert Ali-CCP facts confidently and will mislead anything that reads them until rewritten.
