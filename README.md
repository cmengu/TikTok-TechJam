# beating-nise

A two-person harness that searches for improvements over NISE on Ali-CCP: agents propose, the runner executes, and a frozen hashed protocol plus measurement decide what is believed. Build order is skeleton-first (phase 0), then protocol/events, fake run + app, synthetic task, runner, measure, tree, agents, Ali-CCP ingest, outputs/audit, and rulebook post-checks.

Companion: [Harness Decisions](https://claude.ai/code/artifact/2651312a-1762-421b-b00f-7602c0bac669).

**Phases:** 0 skeleton · 1 protocol + events · 2 fake run + server · 3 synthetic + candidate · 4 runner · 5 measure · 6 tree · 7 agents · 8 Ali-CCP · 9 outputs + audit · 10 rulebook post-checks.

## Measurement

Per-candidate false-promotion rate ≈ 3% nominal (one-sided α = 0.05 × the fraction that reach replicate).
