# Runbook: triaging a failed (or suspiciously successful) run

Work top to bottom. Each step says where to look and what the common causes are. Every error
message quoted here was produced by this repo's own runs; the case study or incident that shows it
in context is linked.

## 0. Find the run and the failing task

```bash
ls -t _runs/<label>/ | head -3              # newest run directory; _LAST points at it
cat _runs/<label>/_LAST/error.json          # which call failed, exit status, stderr path
```

miniwdl writes one directory per call (`call-<Task>[-<shard>]`). In each: `command` (the exact
script that ran), `stderr.txt`, `stdout.txt`, `task.log`, `work/` (files as the task saw them) and,
if the task finished, `out/` and `resources.json`.

If the run **succeeded** but the report looks wrong (an empty table, far fewer variants than
usual), go to step 5.

## 1. Did it fail before any task ran?

| Symptom | Cause | Fix |
|---|---|---|
| `No such input to ReleaseValidation: ReleaseValidation.run_label` | On the miniwdl command line, inputs take no workflow prefix (the JSON file does use it) | `run_label=x`, not `ReleaseValidation.run_label=x` |
| `miniwdl check` errors | WDL syntax or type error | `make wdl-check`; fix and re-run |
| Tasks sit in "no suitable node (insufficient resources on 1 node)" | A task asks for more CPU or memory than the machine has. miniwdl waits; it does not fail | Lower `cpu`/`memory_gb` for that task, or run on a bigger machine |

## 2. Did it fail fetching data?

Tasks: `FetchReference`, `FetchReadsSlice`.

| Symptom (in `stderr.txt`) | Cause | Fix |
|---|---|---|
| `[E::easy_errno] Libcurl reported error 60 (SSL peer certificate or SSH remote key was not OK)` then `Failed to open file "https://..."` | The container has no CA certificate bundle (seen with `staphb/samtools:1.24`), so HTTPS cannot be verified | Use an image with CA certificates; this repo uses the biocontainers samtools and bcftools images for this reason |
| `Failed to open file` with no libcurl error 60 | Wrong URL, file moved, or no network | `curl -sI <url>`; check `config/data_manifest.tsv` |
| Run is slow at this step | Streaming a slice of a remote BAM; speed is set by the network | Expected: about 20 s for the `ci` slice on a fast link. Cache the slice locally with `reads_bam`/`reads_bai` for repeated runs |

## 3. Did preflight stop it?

Task: `Preflight` (only when `run_preflight: true`). Read `work/preflight.md` in the call
directory; each finding names its check ID, and `preflight explain <ID>` gives the details.

| Check | Meaning | Usual fix |
|---|---|---|
| `BED003` | BED chromosome names not in the reference, often `20` against `chr20` ([CS-02](../case-studies/CS-02-contig-names.md)) | `preflight fix-bed --add-chr in.bed --out fixed.bed` |
| `REF001` | Reads and reference are different genome builds (same name, different length) | Get reads and reference from the same build |
| `REF002` (warning) | Reads header lists contigs the reference lacks | Usually harmless for GATK 4.7 and DeepVariant 1.10; the run continues |

Exit codes: 0 pass, 2 warnings only (the run continues), 1 errors or 3 tool error (the run stops).

## 4. Did it fail in calling or benchmarking?

| Symptom | Cause | Fix |
|---|---|---|
| `A USER ERROR has occurred: Input files reference and reads have incompatible contigs: Found contigs with the same name but different lengths` (GATK) | Reads aligned to a different build from the reference | As `REF001` above. Do not "fix" by editing headers: the coordinates differ |
| `exit status 137, a possible indication that it ran out of memory`; `stderr.txt` ends with `Killed ... run_deepvariant.py` | The task hit its memory limit. `config/miniwdl.cfg` enforces `runtime.memory` as a hard limit, as a cloud VM would | Raise `deepvariant_memory_gb`, or lower `deepvariant_shards` (memory scales with shards). See [CS-03](../case-studies/CS-03-deepvariant-memory.md) for measured sizes |
| `stderr.txt` starts with `error: a DeepVariant process was killed for running out of memory` | Same cause, caught by the task's OOM watch, which stops the task at once | As above |
| DeepVariant sits at 0% CPU after `call_variants` starts, then exits 247 with `_queue.Empty` in `stdout.txt` and no error | Also out of memory: one worker was killed and another waited about five minutes for it. Seen before the OOM watch was added; the cgroup's `memory.events` shows `oom_kill 1` | As above ([CS-03](../case-studies/CS-03-deepvariant-memory.md)) |
| hap.py fails reading a VCF | Query VCF is empty or not bgzipped and indexed | Check `NormalizeQuery` output: `bcftools view -H <vcf> \| head` |

Exit status 137 is the kernel's OOM kill (128 + signal 9). On a cloud backend the same failure may
appear as a preempted or "killed" task instead.

## 5. The run succeeded, but the results are wrong or empty

| Symptom | Cause | Fix |
|---|---|---|
| `SummarizeMetrics` fails with `error: no truth variants inside the benchmark regions for gatk. Check that the BED files, truth VCF and reference use the same chromosome names` | The benchmark BED matched nothing, usually a naming mismatch (CS-02). Before this check was added, the run "succeeded" with an empty table | Run `ngs-preflight` on the BEDs and reference |
| `make gate` fails with "F1 could not be computed" or "stratum missing from candidate" | Same as above, or a stratification BED missing from the inputs | Compare `inputs/<profile>.json` with the baseline run's |
| `make gate` fails: "TP changed by X% with identical tool images and parameters" | Same images and parameters, different results: non-determinism or changed input data | Re-run once. If it reproduces, re-check the downloads against the manifest MD5s (`python3 scripts/fetch_data.py download`) and re-run `make data` |
| `make gate` fails with F1 drops and "Tool images and parameters identical: no" | A real regression from the change under test ([INC-01](../incidents/INC-01-mapq-default-change.md)) | Do not update the baseline. Follow the [release-validation runbook](release-validation.md) |

## 6. When to escalate to engineering

Escalate, with the run directory path, `error.json` and the failing call's `stderr.txt`, when:

- the same inputs passed on the previous release and fail now, with no change in `inputs/`;
- a task fails with an error not in this runbook (then add it here once solved);
- the gate reports non-determinism that reproduces;
- results may already have been delivered to a customer (treat as an incident: [template](../templates/incident.md)).
