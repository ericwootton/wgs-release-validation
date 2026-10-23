# CS-03: "DeepVariant fails after we lowered its memory to save money"

All runs and values are real results. GIAB HG002 was used with the `ci` profile
(`chr20:21800001-22000000`) and DeepVariant 1.10.0. Runs used an 8-core, 15 GB Linux laptop, and
every run requested 4 CPUs. Requested memory was enforced as a hard limit through
`config/miniwdl.cfg` (the same enforcement used on cloud virtual machines). Customers and tickets
are fictional. Use the following to reproduce any row:

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

DeepVariant runs one `make_examples` process per shard, so memory requirements increase with the
number of shards. 1 GiB is right at the memory limit, and whether the kernel kills a process varies
between runs. We reproduced both of the customer's failures, and each occurred once in five runs
using the same configuration. When four shards were used, a process was killed within 19 seconds
(exit code 137). When one shard was used, a later process was killed. The remaining process waited
about five minutes for output which would never arrive before exiting with no message (exit code
247). When eight shards were used at 1 GiB of memory, both runs failed. All completed runs showed
the same accuracy as the default 8 GiB configuration. Furthermore, reducing memory saved nothing
because the smallest 4-vCPU machine in our price list already includes 8 GiB of memory. Currently,
the pipeline monitors for processes killed due to insufficient memory. When this is detected, it
fails with a message which clearly identifies memory as the cause.

## 2. Impact

- Failed runs cost money and time. During this silent failure, the 4-vCPU machine had already
  been in use for 377 seconds before the rerun began. This was more than 5 times the time
  required for a successful run.
- No wrong results. Every configuration that finished produced identical calls (below).
- Customers who reduce memory capacity below that required for their shard count are at risk on
  any backend. Since failures occur intermittently, a few successful tests do not establish
  that the configuration is safe.

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

Furthermore, miniwdl reported
`exit status 137, a possible indication that it ran out of memory`. 137 equals 128 + 9. This
means that the kernel's OOM termination mechanism sent SIGKILL. This situation is easy to
diagnose.

**1 shard, 1 GiB: exit 247 after 377 s.** `make_examples` completed (36.9 s), and `call_variants`
then started. Its `time` line appeared after 29.9 s, indicating that the main process had ended by
that point. However, no errors appeared afterwards. The subprocess used for writing continued to
wait in the queue, and CPU usage fell to zero. After 5 minutes, the process terminated:

```text
Process ForkProcess-1:
  File ".../deepvariant/call_variants.py", line 561, in post_processing
  File "/usr/lib/python3.10/multiprocessing/queues.py", line 114, in get
    raise Empty
_queue.Empty
```

The container's cgroup recorded the cause, which the logs never mention. `memory.events` showed
`oom_kill 1`. Exit 247 is not documented anywhere as an out-of-memory code, so a customer has no
way to connect it to the memory setting.

### Step 2: the sweep

Only the DeepVariant task is included, one run per row. Wall time came from the task's own
`resources.json`. The three DeepVariant steps were timed from `stdout.txt`.

| Shards | Memory | Result | Task wall (s) | CPU (s) | make_examples | call_variants | postprocess | Peak memory |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 4 | 1 GiB | exit 137, killed in make_examples | 19 | | | | | |
| 1 | 1 GiB | exit 247 after a silent 5-minute wait | 377 | | 36.9 s | killed | | |
| 2 | 1 GiB | OK | 110.7 | 142.5 | 37.1 s | 43.7 s | 14.3 s | 1.00 GiB (at limit) |
| 4 | 2 GiB | OK | 68.3 | 139.0 | 22.7 s | 27.1 s | 11.2 s | 2.00 GiB (at limit) |
| 1 | 8 GiB | OK | 75.3 | 84.3 | 29.3 s | 29.3 s | 10.0 s | 1.62 GiB |
| 2 | 8 GiB | OK | 87.6 | 122.2 | 28.7 s | 37.0 s | 13.0 s | 1.86 GiB |
| 4 | 8 GiB (default) | OK | 69.5 | 145.9 | 26.2 s | 26.4 s | 9.9 s | 1.99 GiB |

Accuracy was identical in all 5 successful runs. There were 21 missed SNPs and 0 false calls
(F1 of 96.996%), while INDEL F1 was 100%.

What to read from this:

- **Peak memory "at the limit" does not mean the task needed that much.** cgroup `memory.peak`
  includes file cache which the kernel fills to the limit and reclaims under memory pressure. For
  rows which ended at exactly 1.00 or 2.00 GiB, memory was under pressure at that point and had
  not been exhausted. The 8 GiB rows showed the amount of memory required for the actual run.
  This was about 1.6 GiB for 1 shard and 2.0 GiB for 4 shards.
- **Squeezing did not reliably cost time.** Runtime for the 2-shard run at 1 GiB was 26% longer
  than at 8 GiB (110.7 s compared to 87.6 s). This difference arose mainly from `call_variants`.
  However, repeated runs in Step 3 using 1 and 4 shards at 1 GiB took about 70 s. They were no
  slower than under the default conditions. Since each row was run only 1 time, a slight slowdown
  cannot be distinguished from noise between runs (see below).
- **On a small region, shards hardly matter.** `make_examples` is the only step which runs in
  parallel and accounts for a third of the total runtime here. This step accounts for most of the
  total runtime in whole-genome analyses. Therefore, shards and their associated memory
  requirements become important.
- **CPU is the real cost lever.** Using 1 shard consumed 84 CPU seconds, while using 4 shards
  consumed 146 CPU seconds. Completion was only 6 s later with one shard. For smaller regions,
  asking for fewer vCPUs, with a matching shard count, is what saves money. Asking for less memory
  is not.

Actual runtime also varies depending on the other work being processed by the machine. In a
previous run while other containers were processing tasks, the same 4-shard, 8 GiB task took
100.3 s (peak 2.31 GiB).

### Step 3: repeating the failures

Following the pipeline change in Section 7, we ran both failing settings four more times each.
To test this change, we also added the 1 GiB, 8 shards configuration which we expected to
fail. Since the change only reads the counter every 2 seconds, task memory usage will not
change.

| Shards | Memory | Runs | Result | Task wall (s) | CPU (s) | Peak memory |
|---:|---:|---:|---|---:|---:|---:|
| 4 | 1 GiB | 4 | all OK | 70.2 to 72.3 | 133 to 141 | 1.00 GiB (at limit) |
| 1 | 1 GiB | 4 | all OK | 70.2 to 72.2 | 78 to 80 | 1.00 GiB (at limit) |
| 8 | 1 GiB | 2 | both killed in make_examples, exit 137, about 25 s into DeepVariant | | | |

Accuracy was the same as with the default settings in all 8 completed runs.

This means that each of the customer's failures occurred in 1 of the 5 runs under its
corresponding configuration. At 1 GiB, the task is just at its limit. The kernel continuously
reclaims the file cache to avoid exceeding the limit. Processes are forcibly terminated only when
their peak memory usage coincides. A set of only 5 runs is insufficient to estimate the failure
rate. However, failures will still recur when processing hundreds of samples in batches, even at
a rate far below 1 in 5. When 8 shards were used, the 2 runs each failed about 25 s after
starting.

### Step 4: what the memory setting costs

Costs are calculated using `config/prices.yaml` (AWS us-east-1, retrieved 2026-10-22). This task
requires 4 vCPU. The smallest 4-vCPU machine listed is `c6i.xlarge` which has 8 GiB of memory.
Therefore, the same machine is used even when 1 GiB or 2 GiB of memory is requested. Only runtime
changes.

| Configuration | Task wall (s) | On demand ($0.170/h) | Spot ($0.0748/h, medium confidence) |
|---|---:|---:|---:|
| 4 shards, 8 GiB (default) | 69.5 | $0.0033 | $0.0014 |
| 4 shards, 1 GiB, when it finished (median of 4) | 70.3 | $0.0033 | $0.0015 |
| 4 shards, 1 GiB, killed (then re-run) | 19 | $0.0009 | $0.0004 |
| 1 shard, 1 GiB, silent failure (then re-run) | 377 | $0.0178 | $0.0078 |

For 1 region of 200 kb, these amounts were all below 1 cent, but they increase in proportion to
processing volume. The ratios are the main consideration. Reducing memory saved nothing when
processing succeeded. When processing failed, the sample still had to be rerun. Therefore, the cost
of wasted time was added to the cost of a successful run. Immediate forced termination cost about
1.3 times as much as a successful run, while silent failure cost about 6.4 times as much.

## 5. Root cause

**What failed:** memory was capped at a level which only just met DeepVariant's requirements for
this shard count. Therefore, the kernel forcibly terminated one of its processes in some runs.
**Why it was difficult to detect:** Depending on which process was terminated, the task either
failed immediately with 137 or hung and then exited with 247 without a message. Nothing in the
pipeline converted cgroup OOM records into messages. Since some runs were affected while others
were not, a test run or two at 1 GiB could easily have passed. **Why it happened at all:**
Lowering memory looks like a free saving. Nothing told the customer it was not.

## 6. Resolution

Restoring the default settings of 8 GiB and 4 shards is recommended. We completed one run using 2
GiB and 4 shards, but peak usage reached the limit. However, Step 3 shows that a single
successful run provides very limited evidence. The customer restored the defaults, and the rerun
of the previously failed sample completed within the usual time.

## 7. Prevention

- **The task now watches for an OOM kill and names it.** The DeepVariant task in
  `wdl/tasks/call.wdl` reads the container's `oom_kill` counter (`/sys/fs/cgroup/memory.events`)
  every 2 seconds while DeepVariant is running. If the counter increases, the task prints a
  message, stops DeepVariant, and fails. If DeepVariant exits with an error, the task reads the
  counter again. This checks for a forced termination which may have occurred less than one check
  interval before exit.

  Since the silent hang did not recur in 4 reruns (Step 3), we tested the change at 1 GiB
  using 8 shards. Both runs were killed. Each stopped about 25 s after DeepVariant started and
  returned exit code 137. `stderr.txt` now ends with:

  ```text
  /opt/deepvariant/bin/run_deepvariant: line 2:    18 Killed    /usr/bin/python3 -u /opt/deepvariant/bin/run_deepvariant.py "$@"
  error: a DeepVariant process was killed for running out of memory (memory_gb=1, shards=8). Raise deepvariant_memory_gb or lower deepvariant_shards; see docs/case-studies/CS-03-deepvariant-memory.md
  ```

  Since the main process was killed in those runs, they would have failed quickly in any case. This
  change added a message in that situation. Since we had not observed another actual DeepVariant
  hang, we used a substitute script to test a different situation. In this case, a worker was killed
  while the remaining processes continued waiting. We ran a small script in the DeepVariant image
  with the container memory limit set to 300 MB. It started a child process which continued
  allocating memory until it was killed by the kernel. Then, the script waited indefinitely in the
  same way as the hanging runs. The guard printed the message and stopped the script 4 s after the
  kill. This task ended with exit code 143, and no processes remained. When nothing was killed, the
  same script exited normally. For ordinary failures with no OOM kill, the guard printed no message
  and returned the original failure exit code unchanged.

  DeepVariant runs in its own process group (`setsid`), so the guard stops only DeepVariant and
  its worker processes. After this change, runs using the default settings still achieved the same
  accuracy (SNP F1 97.00%). The run with 8 shards at 1 GiB failed again and displayed the message
  above.
- **The triage runbook has both signatures.** It covers exit code 137 with `Killed`. It also
  covers exit code 247 or a long stall at 0% CPU after `call_variants` starts
  ([failed-run-triage.md](../runbooks/failed-run-triage.md)).
- **For production deployments.** Set the task timeout well above the time a run usually takes
  (the Cromwell runtime attribute `maxRetries` with the workflow option `memory_retry_multiplier`
  can retry with more memory automatically). Also set an alert for a task at 0% CPU for more than a
  few minutes. This catches other hangs too.
- **Documented sizing.** `deepvariant_memory_gb` in `wdl/main.wdl` now points to this page. Keep
  the default value. Setting memory below 8 GiB on a 4-vCPU machine saves nothing, and 1 GiB is
  already at the edge with 1 to 4 shards. Peak usage recorded with 4 shards (file cache included)
  was about 2 GiB on this 200 kb region. It was 6.9 to 7.9 GiB in 3 runs on the 5 Mb `full` region.
  The higher value is close to the 8 GiB limit, but none of these runs failed. So most of it is
  likely cache which the kernel can reclaim. Whole genomes have not been measured here, so measure
  usage before setting memory below the default or using more than 4 shards.

## 8. Customer-facing reply

> Hi Jordan,
>
> Thank you for the exit codes and the run directories. They made this quick to pin down.
>
> Both failures come from the 1 GiB memory setting. DeepVariant runs several worker processes at
> the same time. At 1 GiB, the system sometimes stopped one of them for using too much memory.
> Exit code 137 is the usual sign of this. Exit code 247 after a long pause is the same problem.
> But the remaining process waited a few minutes before giving up and never said why. That part
> was a gap in our pipeline. It now checks for this and fails with a message stating that memory
> was the cause.
>
> One thing worth knowing is that failures at 1 GB come and go. We ran each of your 2 settings 5
> times, and each failed once. So a few successful runs at a low setting do not mean it is safe
> across a whole batch.
>
> The good news is that you can go back to the default without paying more. With 4 CPUs, the
> smallest standard cloud machine already has 8 GB of memory. So asking for 1 GB was buying the
> same machine. In our tests, the lower setting saved nothing when it worked. A failed run cost
> the wasted time plus a full re-run. Your results are unaffected. Every run that finished gave
> identical calls.
>
> If you'd like to tune cost further, the setting that matters is the number of CPUs. I'm happy to
> look at your sample sizes with you.
>
> Best regards,
> Customer Success
