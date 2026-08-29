# Synthetic CTR/CVR benchmark — competitor brief

You are improving a candidate model on a synthetic impression dataset. The harness
scores click-through rate (CTR) and conversion rate (CVR) on a fixed
search-validation split. Training data and validation features are available to
the candidate; hidden evaluation splits are scored only by the harness.

## Task

- Predict `p_click` on every impression.
- Predict `p_conversion_given_click` on clicked rows only.
- Feature engineering and model architecture changes are in scope.
- Do not read labels from paths you are not given in `TRAIN` / `VALID`.

## Reporting

Each hypothesis should cite prior work or `"no prior"`, estimate `expected_gain`
(AUC delta on the primary metric), and `expected_gpu_h` for a screen run.

<!-- brief-end -->
