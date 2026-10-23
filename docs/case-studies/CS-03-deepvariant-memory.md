# CS-03: "DeepVariant fails after we lowered its memory to save money"

All runs and numbers are real: GIAB HG002, `ci` profile (`chr20:21800001-22000000`), DeepVariant
1.10.0, 4 CPUs requested in every run, on an 8-core, 15 GB Linux laptop with `config/miniwdl.cfg`
enforcing the requested memory as a hard limit (as a cloud VM would). The customer and ticket are
fictional. Reproduce any row with:

```bash
make run PROFILE=ci LABEL=cs03-s<shards>-m<gib> \
  EXTRA="run_preflight=false callers=deepvariant deepvariant_memory_gb=<gib> deepvariant_shards=<shards>"
```

| Field | Value |
|---|---|
| Ticket ID | CS-03 |
| Date opened / closed | 2026-10-22 / 2026-10-23 |
| Severity | P2 (one customer's runs failing; workaround available) |
| Customer | Harbour Point Biobank, cloud deployment (fictional) |
| Reported symptom | "To cut cost we set `deepvariant_memory_gb` to 1. Some runs now fail with exit 137. One sat doing nothing for six minutes and then failed with exit 247 and no error at all." |

## 1. Summary

DeepVariant runs one `make_examples` process per shard, so its memory need grows with the shard
count. At 1 GiB it sits right at the limit, and whether the kernel kills one of its processes
varies from run to run. We reproduced both of the customer's failures, and each happened once in
five runs of the same setting. With four shards a process was killed within 19 seconds (exit 137).
With one shard a later process was killed, and the remaining process waited about five minutes for
output that would never come, then exited 247 with no message. Eight shards at 1 GiB failed in both
runs. Every run that finished gave the same accuracy as the default 8 GiB, and lowering memory
saved nothing: the smallest 4-vCPU machine in our price list already has 8 GiB. The pipeline now
watches for an out-of-memory kill and, when it sees one, fails with a message that names memory as
the cause.

## 2. Impact

- Failed runs cost money and time: the silent failure held a 4-vCPU machine for 377 seconds, more
  than 5 times a successful run, before a re-run was even started.
- No wrong results: every configuration that finished produced identical calls (below).
- Any customer who lowers memory below what their shard count needs is exposed, on any backend.
  Because the failures are intermittent, a few good test runs do not show that a setting is safe.

## 3. Timeline

| When | What |
|---|---|
| 22:52 | Reported via the support portal, with the two exit codes |
| 23:22 | Reproduced both failures on the `ci` region |
| 23:52 | Sweep of shard count and memory finished (table below) |
| 00:10 | Workaround sent: back to the default 8 GiB; pipeline change raised |
| 01:15 | Pipeline change tested; repeat runs show the 1 GiB failures are intermittent |

## 4. Investigation

### Step 1: the two failures

**4 shards, 1 GiB: exit 137 after 19 s.** `stderr.txt` ends with

```text
/opt/deepvariant/bin/run_deepvariant: line 2:    14 Killed    /usr/bin/python3 -u /opt/deepvariant/bin/run_deepvariant.py "$@"
```

and miniwdl reports `exit status 137, a possible indication that it ran out of memory`. 137 is
128 + 9: the kernel's OOM killer sent SIGKILL. This one is easy to diagnose.

**1 shard, 1 GiB: exit 247 after 377 s.** `make_examples` finished (36.9 s) and `call_variants`
started. Its `time` line appeared after 29.9 s, meaning the main process had gone, but no error
followed. A writer subprocess kept waiting on a queue, CPU use fell to zero, and five minutes later
the process exited:

```text
Process ForkProcess-1:
  File ".../deepvariant/call_variants.py", line 561, in post_processing
  File "/usr/lib/python3.10/multiprocessing/queues.py", line 114, in get
    raise Empty
_queue.Empty
```

The container's cgroup recorded the cause, which the logs never mention: `memory.events` showed
`oom_kill 1`. Exit 247 is not documented anywhere as an out-of-memory code, so a customer has no
way to connect it to the memory setting.

### Step 2: the sweep

DeepVariant task only, one run per row; wall time from the task's own `resources.json`. The three
DeepVariant steps are timed from `stdout.txt`.

| Shards | Memory | Result | Task wall (s) | CPU (s) | make_examples | call_variants | postprocess | Peak memory |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 4 | 1 GiB | exit 137, killed in make_examples | 19 | | | | | |
| 1 | 1 GiB | exit 247 after a silent 5-minute wait | 377 | | 36.9 s | killed | | |
| 2 | 1 GiB | OK | 110.7 | 142.5 | 37.1 s | 43.7 s | 14.3 s | 1.00 GiB (at limit) |
| 4 | 2 GiB | OK | 68.3 | 139.0 | 22.7 s | 27.1 s | 11.2 s | 2.00 GiB (at limit) |
| 1 | 8 GiB | OK | 75.3 | 84.3 | 29.3 s | 29.3 s | 10.0 s | 1.62 GiB |
| 2 | 8 GiB | OK | 87.6 | 122.2 | 28.7 s | 37.0 s | 13.0 s | 1.86 GiB |
| 4 | 8 GiB (default) | OK | 69.5 | 145.9 | 26.2 s | 26.4 s | 9.9 s | 1.99 GiB |

Accuracy was identical in all five successful runs: SNP 21 missed, 0 false calls, F1 96.996%;
INDEL F1 100%.

What to read from this:

- **Peak memory "at the limit" does not mean the task needed that much.** The cgroup's
  `memory.peak` counts file cache, which the kernel fills up to the limit and reclaims under
  pressure. Rows that finished at exactly 1.00 or 2.00 GiB were squeezed, not starving. The 8 GiB
  rows show the real working size: about 1.6 GiB with one shard and 2.0 GiB with four.
- **Squeezing did not reliably cost time.** The 2-shard, 1 GiB run took 26% longer than at 8 GiB
  (110.7 s against 87.6 s), mostly in `call_variants`. But the repeats in Step 3, at 1 and 4 shards
  with 1 GiB, took about 70 s, no slower than the default. One run per row cannot separate a small
  slowdown from the run-to-run noise (below).
- **On a small region, shards hardly matter.** `make_examples` is the only step that runs in
  parallel, and here it is a third of the time. On a whole genome it dominates, so there shards do
  matter, and so does the memory that comes with them.
- **CPU is the real cost lever.** One shard used 84 CPU-seconds against 146 for four, and finished
  only 6 s later. On a small region, asking for fewer vCPUs (with a matching shard count) is what
  saves money; asking for less memory is not.

Wall times also move with whatever else the machine is doing: the same 4-shard, 8 GiB task took
100.3 s (peak 2.31 GiB) in an earlier run while other containers were busy.

### Step 3: repeating the failures

After the pipeline change in section 7, we ran both failing settings four more times each, and
added 8 shards at 1 GiB, a setting we expected to fail, to test the change. The change
only reads a counter every 2 seconds, so it does not change how much memory the task uses.

| Shards | Memory | Runs | Result | Task wall (s) | CPU (s) | Peak memory |
|---:|---:|---:|---|---:|---:|---:|
| 4 | 1 GiB | 4 | all OK | 70.2 to 72.3 | 133 to 141 | 1.00 GiB (at limit) |
| 1 | 1 GiB | 4 | all OK | 70.2 to 72.2 | 78 to 80 | 1.00 GiB (at limit) |
| 8 | 1 GiB | 2 | both killed in make_examples, exit 137, about 25 s into DeepVariant | | | |

All eight runs that finished had the same accuracy as the default.

So each of the customer's failures happened once in five runs of its setting. At 1 GiB the task
is right at the edge. The kernel keeps reclaiming file cache to stay under the limit, and a
process is killed only when the processes' memory peaks happen to coincide. Five runs are too few
to give a failure rate. Across a batch of hundreds of samples, though, even a rate well below one
in five means regular failures. With 8 shards it failed in both runs, about 25 s in.

### Step 4: what the memory setting costs

Priced from `config/prices.yaml` (AWS us-east-1, retrieved 2026-10-22). The task asks for 4 vCPUs.
The smallest 4-vCPU machine listed there, `c6i.xlarge`, has 8 GiB, so asking for 1 or 2 GiB buys
the same machine. Only the time changes.

| Configuration | Task wall (s) | On demand ($0.170/h) | Spot ($0.0748/h, medium confidence) |
|---|---:|---:|---:|
| 4 shards, 8 GiB (default) | 69.5 | $0.0033 | $0.0014 |
| 4 shards, 1 GiB, when it finished (median of 4) | 70.3 | $0.0033 | $0.0015 |
| 4 shards, 1 GiB, killed (then re-run) | 19 | $0.0009 | $0.0004 |
| 1 shard, 1 GiB, silent failure (then re-run) | 377 | $0.0178 | $0.0078 |

For one 200 kb region these are fractions of a cent, but they scale linearly with the work. The
point is the ratios. When it worked, lowering memory saved nothing. When it failed, the sample still
had to be re-run, so a failure cost the wasted time on top of a good run: about 1.3 times a good
run for the immediate kill, and about 6.4 times for the silent one.

## 5. Root cause

**What failed:** the memory limit was at the edge of what DeepVariant needs for the shard count,
so in some runs the kernel killed one of its processes. **Why it was hard to see:** depending on
which process died, the task either failed at once with 137 or hung and exited 247 without a word,
and nothing in the pipeline turned the cgroup's OOM record into a message. Because it happened in
some runs and not others, a test run or two at 1 GiB could easily have passed. **Why it happened at
all:** lowering memory looks like a free saving, and nothing told the customer it was not.

## 6. Resolution

Advised going back to the default of 4 shards with 8 GiB. 2 GiB with 4 shards finished in the one
run we made, but its peak was at the limit, and Step 3 shows how little one good run proves. The
customer went back to the default; their failed sample re-ran in the normal time.

## 7. Prevention

- **The task now watches for an OOM kill and names it.** The DeepVariant task in
  `wdl/tasks/call.wdl` reads the container's `oom_kill` counter (`/sys/fs/cgroup/memory.events`)
  every 2 seconds while DeepVariant runs. If the counter goes up, the task prints a message, stops
  DeepVariant, and fails. If DeepVariant exits with an error, the task reads the counter once
  more, in case the kill came less than one check before the exit.

  The silent hang did not happen again in four repeats (Step 3), so we tested the change on
  8 shards with 1 GiB, which was killed in both runs we made. Both stopped with exit 137 about
  25 s into DeepVariant, and `stderr.txt` now ends with:

  ```text
  /opt/deepvariant/bin/run_deepvariant: line 2:    18 Killed    /usr/bin/python3 -u /opt/deepvariant/bin/run_deepvariant.py "$@"
  error: a DeepVariant process was killed for running out of memory (memory_gb=1, shards=8). Raise deepvariant_memory_gb or lower deepvariant_shards; see docs/case-studies/CS-03-deepvariant-memory.md
  ```

  In those runs the killed process was the main one, so they would have failed quickly anyway. What
  the change adds there is the message. We have not seen a real DeepVariant hang again, so the
  other case, where a worker is killed and the rest wait, was tested with a stand-in. A small script
  in the DeepVariant image, under a 300 MB container limit, started a child that allocated memory
  until the kernel killed it, then waited forever, as the hung run did. The guard printed the
  message and stopped the script 4 s after the kill, the task exited with 143, and no processes
  were left behind. The same script exited normally when nothing was killed, and an ordinary
  failure with no OOM kill passed its own exit code through with no message.

  DeepVariant runs in its own process group (`setsid`), so the guard stops only DeepVariant and
  its workers. After that change the default run gave the same accuracy (SNP F1 97.00%), and 8 shards
  at 1 GiB again failed with the message above.
- **The triage runbook has both signatures:** exit 137 with `Killed`, and exit 247 or a long
  stall at 0% CPU after `call_variants` starts
  ([failed-run-triage.md](../runbooks/failed-run-triage.md)).
- **For production deployments:** set a task timeout well above the normal time (Cromwell's
  `maxRetries` runtime attribute with the `memory_retry_multiplier` workflow option can retry
  with more memory automatically), and
  alert on a task at 0% CPU for more than a few minutes, which catches other hangs too.
- **Documented sizing:** `deepvariant_memory_gb` in `wdl/main.wdl` now points here. Leave it at
  the default: on a 4-vCPU machine nothing is saved below 8 GiB, and 1 GiB was at the edge with 1
  to 4 shards. With 4 shards the recorded peak (file cache included) was about 2 GiB on this
  200 kb region and 6.9 to 7.9 GiB in three runs on the 5 Mb `full` region. The higher figure is
  close to the 8 GiB limit, but most of it is likely cache the kernel can reclaim, since none of
  those runs failed. Whole genomes have not been measured here, so measure before going below the
  default, or above 4 shards.

## 8. Customer-facing reply

> Hi Jordan,
>
> Thanks for the exit codes and the run directories; they made this quick to pin down.
>
> Both failures come from the 1 GiB memory setting. DeepVariant runs several worker processes at
> once, and at 1 GiB the system sometimes stopped one of them for using too much memory. Exit 137
> is the usual sign of that. Exit 247 after a long pause is the same problem, but the remaining
> process waited a few minutes before giving up and never said why. That part was a gap in our
> pipeline: it now checks for this and fails with a message that says memory was the cause.
>
> One thing worth knowing: at 1 GB the failures come and go. We ran each of your two settings five
> times, and each failed once. So a few good runs at a low setting do not mean it is safe across a
> whole batch.
>
> The good news is you can go back to the default without paying more. With 4 CPUs, the smallest
> standard cloud machine already has 8 GB of memory, so asking for 1 GB was buying the same machine.
> In our tests the lower setting saved nothing when it worked, and a failed run cost the wasted time
> plus a full re-run. Your results are unaffected: every run that finished gave identical calls.
>
> If you'd like to tune cost further, the setting that matters is the number of CPUs, and I'm happy
> to look at your sample sizes with you.
>
> Best regards,
> Customer Success
