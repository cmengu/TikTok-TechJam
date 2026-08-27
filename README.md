# beating-nise

A two-person harness that searches for improvements over NISE on Ali-CCP: agents propose, the runner executes, and a frozen hashed protocol plus measurement decide what is believed. Build order is skeleton-first (phase 0), then protocol/events, fake run + app, synthetic task, runner, measure, tree, agents, Ali-CCP ingest, outputs/audit, and rulebook post-checks.

Companion: [Harness Decisions](https://claude.ai/code/artifact/2651312a-1762-421b-b00f-7602c0bac669).

**Phases:** 0 skeleton · 1 protocol + events · 2 fake run + server · 3 synthetic + candidate · 4 runner · 5 measure · 6 tree · 7 agents · 8 Ali-CCP · 9 outputs + audit · 10 rulebook post-checks.

## Running the app

```
source .venv/bin/activate
python -m app          # or: python -m app.server
```

Serves on http://127.0.0.1:8000 with reload. Point it at a live run by
starting `python -m harness fake --speed 20` in a second shell.
