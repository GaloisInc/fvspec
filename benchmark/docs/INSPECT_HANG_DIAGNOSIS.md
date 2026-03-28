# inspect_ai hang diagnosis (2026-03-27)

## Incident

A benchmark generation run (`fvspec -n 250 -s 100`, Sonnet 4.6, `max_samples=16` parallelism) ran for 17+ hours, completed ~50 samples across several run dirs, then stalled. The main thread was spinning at 99.6% CPU with zero progress — no new files written for 7+ hours. All 29 worker threads were sleeping on futex waits.

```
Thread 145115: state=R wchan=0         # main thread: spinning in userspace
Thread 145145: state=S wchan=futex_do_wait  # worker: idle
Thread 145146: state=S wchan=futex_do_wait  # worker: idle
... (29 more sleeping threads)
```

The process had to be killed via signal.

## Root cause analysis

We searched the inspect_ai issue tracker and found three relevant issues documenting similar behavior.

### UKGovernmentBEIS/inspect_ai#2487 — "Inspect always hangs at last question"

Most relevant. Multiple users report evals hanging on the last 1-2 samples with high CPU. @mdarcy220 identified two root causes:

1. **Model API hangs** — Certain API requests hang indefinitely. The `--timeout` flag didn't work for some providers in older versions (fixed in 0.3.121). Due to parallel execution, other workers finish while one sample is frozen, making it *appear* like the hang happens at the end. But the frozen sample could have gotten stuck at any point.

2. **SSE parsing bug in MCP** — An [httpx-sse bug](https://github.com/florimondmanca/httpx-sse/issues/34) could cause infinite hangs during MCP tool calls.

A separate observation from the same thread: when the `.eval` file grows to hundreds of MB, the **post-run serialization** (`model_validate` on samples) causes near-100% CPU for hours. This matches a "successful but spinning" process.

### UKGovernmentBEIS/inspect_ai#849 — "Inspect sometimes hangs on extremely large runs"

Root cause was **threading deadlocks** in log reading/writing, particularly with S3 and sync/async wrappers. The maintainer (jjallaire) eliminated threading and moved to async-only APIs. Closed as fixed, but the deadlock pattern (main thread stuck, workers sleeping) is similar to what we observed.

### UKGovernmentBEIS/inspect_ai#2747 — "Add default value for message_limit"

Open issue. `message_limit` defaults to `None`, meaning tool-call loops (`tool_calls="loop"`) can run forever — burning credits and potentially wedging the event loop if a model enters an infinite tool-call cycle.

## Our likely cause

The benchmark task had **no `message_limit` set**. With `tool_calls="loop"` in the solver, a model could enter an infinite tool-call cycle on a single sample. This would:

1. Keep one worker busy forever on that sample
2. Block the task slot (one of the 16 `max_samples` slots)
3. Eventually, if enough samples get stuck, all worker slots fill with stuck samples and no new samples can start
4. The main thread busy-waits polling the event loop for completions that never come

This matches exactly what we observed: the process completed ~50 samples (across multiple run dirs / retries), then froze with the main thread spinning and all workers sleeping.

## Fix

Set `message_limit` on the Task. We applied this in the baselines pipeline:

```python
return Task(
    ...,
    message_limit=50,
)
```

The benchmark pipeline should do the same. 50 messages (25 assistant turns) is sufficient for the formalization agent — most samples complete in 10-20 tool calls.

## Other mitigations to consider

- **`--timeout`** on `inspect eval` — sets a per-sample wall-clock timeout. Verify it works with the Anthropic provider on our inspect_ai version.
- **`token_limit`** on the Task — caps total tokens per sample.
- **Process-level watchdog** — if no new artifact files are written for N minutes, kill and retry.
- **Upgrade inspect_ai** — several hang-related fixes have landed since 0.3.121.
