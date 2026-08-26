# Build steps

Source of truth for phased implementation. Each phase lists owners, interfaces, tests, and locked decisions.

---

## Phase 1 · Protocol and event log

**Owner** A: `protocol.py` · B: `events.py`  
**Depends on** phase 0  
**Source** Backend_plan §1, §4

### Goal

Load a protocol yaml, hash its ruler block canonically, and write a `run_started` event through a single-writer log that three threads can hammer without a torn line. After this phase you can `tail -f` a real log.

### In scope

`harness/protocol.py`, `harness/events.py`, `harness/__main__.py` (the `init` command only), `tests/test_01_protocol.py`, `tests/test_01_events.py`.

### Out of scope

Filling in any null in `aliccp.yaml`. Any event type other than `run_started` being emitted by real code (tests may emit any type). The web server. Reading the log back.

### Interfaces

```python
# harness/protocol.py
@dataclass
class Protocol:
    task: str
    schema_version: int
    ruler: dict
    run: dict
    protocol_hash: str
    path: Path

def load(path) -> Protocol
    # validates required keys; nulls allowed under ruler

def canonical_bytes(ruler: dict) -> bytes
    # sort keys recursively; floats via repr of float(x) so 0.10 == 0.1;
    # ints stay ints; None -> "null"; no whitespace; utf-8.
    # Comments never reach here (yaml drops them).

def protocol_hash(ruler: dict) -> str
    # "sha256:" + hex of canonical_bytes; run block NOT included


# harness/events.py
class EventLog:
    def __init__(self, run_dir: Path, run_id: str, protocol: Protocol): ...
        # opens events.jsonl and heartbeat.jsonl for append; starts one writer thread
        # first line written is run_started with the whole protocol dict embedded

    def emit(self, type: str, **fields) -> int
        # validates type in EVENT_TYPES and fields.get("state") in STATES if present;
        # requires "summary" (str); stamps schema_version=1, seq, t (ISO-8601 UTC),
        # run, protocol_hash; puts on queue; returns the seq it WILL get
        # (allocated under a lock, so monotonic)

    def new_node(self, parent: int | None) -> int
        # one counter, lock-protected

    def heartbeat(self, worker: str, **fields) -> None
        # goes to heartbeat.jsonl through the same queue

    def close(self) -> None
        # drains, fsyncs, joins thread; emit after close raises

    # writer thread: json.dumps(line) + "\n"; flush() every line;
    # os.fsync only when type in {"verdict","submission_written","run_ended"}


# python -m harness init protocols/synthetic.yaml
#   -> creates runs/<task>-<YYYYMMDD-HHMMSS>/ , writes run_started, closes,
#      prints the run id and hash
```

### Locked decisions (phase 1)

1. **Required keys** — top-level only: `schema_version`, `task`, `ruler`, `run`. Also check `ruler` is a non-empty dict. No nested schema this phase; `ValueError` names the missing key.
2. **`run_started` payload** — raw YAML body `{schema_version, task, ruler, run}` plus `protocol_hash` and `protocol_path` (as a string). Never the dataclass — the browser reads this line and must not see Python types.
3. **`init` output** — two lines: `run_id=<task>-<YYYYMMDD-HHMMSS>` then `protocol_hash=sha256:…`. UTC for the run id and for every `t` stamp.
4. **Heartbeat seq** — separate counter. Heartbeats get their own monotonic `seq` starting at 1 in `heartbeat.jsonl`, plus the same stamps (`schema_version`, `t`, `run`, `protocol_hash`, `type="heartbeat"`, `worker`). No summary required. Reason: the heartbeat endpoint's `?since=` needs its own sequence, and `events.jsonl` line counts must not move.
5. **`test_stubs_raise`** — data-driven: an `IMPLEMENTED = {"harness.protocol", "harness.events"}` set at the top of the test that each phase extends in its own PR; stubs outside the set must still raise.
6. **Ship** — commit when green on branch `phase-1-protocol-events`, open a PR against `main`, do not merge.

**Extras, locked:** `json.dumps(obj, separators=(",", ":"), sort_keys=False, ensure_ascii=False, default=str)`; stamp order `schema_version`, `seq`, `t`, `run`, `protocol_hash`, `type` before the caller's fields; flush every line; fsync on `verdict`, `submission_written`, `run_ended` only.

### Tests to pass — `tests/test_01_protocol.py`

- `test_reorder_same_hash` — the same ruler with top-level keys reordered hashes identically.
- `test_float_formatting_same_hash` — `0.10` and `0.1` and `1e-1` give the same hash.
- `test_comment_same_hash` — a yaml with an added comment line gives the same hash.
- `test_ruler_change_new_hash` — changing `metrics.cvr_auc.population` changes the hash.
- `test_run_block_not_hashed` — changing `run.budget.gpu_hours` leaves the hash unchanged.
- `test_missing_ruler_raises` — a yaml without `ruler` raises a clear `ValueError` naming the key.
- `test_nulls_allowed` — `aliccp.yaml` loads and hashes even with its seven nulls.

### Tests to pass — `tests/test_01_events.py`

- `test_first_line_is_run_started` — after `__init__` + `close`, the file has one line, type `run_started`, containing the protocol dict and hash.
- `test_concurrent_emit_no_torn_lines` — 3 threads × 1000 emits; file has 3001 lines; every line parses as JSON; seq is exactly 1…3001 with no gaps or repeats.
- `test_stamps_present` — every line has `schema_version==1`, `seq`, `t`, `run`, `protocol_hash`, `type`, `summary`.
- `test_unknown_type_raises` — `emit("failed", …)` raises; nothing is written.
- `test_bad_state_raises` — `emit("state_changed", state="failed", …)` raises.
- `test_missing_summary_raises`.
- `test_heartbeat_sidecar` — 10 heartbeats land in `heartbeat.jsonl`; `events.jsonl` line count is unchanged.
- `test_new_node_unique_under_threads` — 4 threads × 500 calls yield 2000 distinct ids.
- `test_close_drains_then_refuses` — line count after close equals emits + 1; emit after close raises.
- `test_seq_monotonic_same_millisecond` — 100 emits in a tight loop have strictly increasing seq even where `t` repeats.

### Gate to phase 2

All tests green. `python -m harness init protocols/synthetic.yaml` creates a run directory; `tail -f runs/<id>/events.jsonl` shows the `run_started` line with the hash printed by the command.

### Hands forward

The only write path to the log. Phase 2's fake run and every later module call `EventLog.emit` and nothing else.
