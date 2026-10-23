# GA4GH standards

Three GA4GH standards decide how a workflow like this one moves between platforms: WES (run a
workflow through an API), TRS (find a workflow in a registry such as Dockstore) and DRS (refer to
data by an ID instead of a bucket path). This page says what was done with each and what was not.

| Standard | Status here |
|---|---|
| WES 1.0 (Workflow Execution Service) | **Run.** The `fixture` and `ci` profiles ran through a local Cromwell 91 WES server and gave the same metrics as miniwdl |
| TRS 2.0 (Tool Registry Service), through Dockstore | **Ready to register.** `.dockstore.yml` lists the four workflows; publishing needs the Dockstore GitHub App installed on the repository |
| DRS 1.x (Data Repository Service) | **Not run.** Inputs given as `drs://` URIs pass through `scripts/cloud_inputs.py` unchanged; resolving them needs a DRS resolver in the engine's configuration |

## WES: the same workflow through a second engine

WES is the API that Terra, AnVIL and other platforms use to accept workflow runs. A run is a
`POST /runs` with the workflow URL and its inputs, then polling `GET /runs/{id}/status`.
`scripts/wes_run.py` does that with the Python standard library, so it works against any WES 1.0
server.

The test is a strict one. `make wes` runs a profile through the WES server, then gates the result
against the miniwdl run of the same profile with `scripts/compare_metrics.py`. The tool images and
parameters are the same, so the gate's exact-match rule applies: every true positive count has to
be identical, not just close.

| Profile | Engine | WES state | Run time (WES log) | Gate against miniwdl |
|---|---|---|---:|---|
| `fixture` (30 kb, 9 tasks) | Cromwell 91, local Docker backend | COMPLETE | 76 s | [PASS, identical](results/fixture-wes/gate.md) |
| `ci` (200 kb, 10 tasks) | Cromwell 91, local Docker backend | COMPLETE | 105 s | [PASS, identical](results/ci-wes/gate.md) |

Each folder also has `wes_run.json`: the run ID, the server's WES and engine versions, the task
names, the task exit codes and the output names, with no server paths.

### How to run it

```bash
# 1. A Cromwell 91 server; its default configuration runs tasks in local Docker.
java -Xmx2g -jar cromwell-91.jar server          # WES at http://localhost:8000/api/ga4gh/wes/v1

# 2. Serve this directory where the server and its task containers can read it. Containers
#    cannot reach 127.0.0.1 on the host, so bind to the Docker bridge address.
python3 -m http.server 8081 --bind 172.17.0.1 --directory .

# 3. Run the profile through WES and gate it against the miniwdl result.
make run PROFILE=fixture                         # the miniwdl result, if not already there
make wes PROFILE=fixture WES_FILES=http://172.17.0.1:8081
```

`make wes` rewrites the inputs so every local file becomes a URL under `WES_FILES`
(`scripts/cloud_inputs.py --target wes`), submits `wdl/main.wdl` by URL (Cromwell resolves its
imports relative to that URL), waits, and writes `docs/results/<profile>-wes/`.

### What came up

- **Cromwell 92 cannot run digest-pinned images on its local backend.** Every task failed with
  `No coercion defined from '…@sha256:…' of type 'cromwell.backend.validation.Containers' to
  'String?'` ([broadinstitute/cromwell#7846](https://github.com/broadinstitute/cromwell/issues/7846)).
  Image tags work, but this workflow pins every image by digest on purpose, and turning off
  Cromwell's hash lookup did not help. Cromwell 91 runs the same workflow unchanged. The issue
  reports the cloud backends as unaffected; the [cloud run](results/cloud-run.md) on GCP Batch
  lists it as a check.
- **Cromwell renames `http://` inputs.** It saves them under hashed file names, and the
  stratification names in the results came from the file names. The workflow now takes the names
  from the input paths before localisation (`strat_names` in `wdl/main.wdl`), so both engines
  report `lowmap_or_segdup`, not a hash.
- **Cromwell saves downloaded inputs readable by its own user only** (mode 600). The
  ngs-preflight image ran as an unprivileged user, so under Cromwell the `Preflight` task could not
  open its BED file, while under miniwdl it could. The image now runs as root, like most images
  used in workflows (the biocontainers, GATK and DeepVariant images do too); run by hand, it takes
  `--user "$(id -u):$(id -g)"` so reports are not owned by root.

## TRS and Dockstore

`.dockstore.yml` at the repository root registers four WDL workflows:

| Dockstore name | Descriptor | Test inputs |
|---|---|---|
| `wgs-release-validation` | `wdl/main.wdl` | `inputs/ci.json`, `inputs/fixture.json` |
| `longread-handoff` | `wdl/optional/longread.wdl` | `inputs/longread.json` |
| `sv-merge` | `wdl/optional/sv_merge.wdl` | none (it needs a finished long-read run) |
| `customer-deliverables` | `wdl/optional/deliverables.wdl` | `inputs/deliverables.json` |

To publish: install the Dockstore GitHub App on the repository from dockstore.org, after which each
push to a branch or tag updates the matching workflow version. Dockstore serves every version
through its TRS API, which is how platforms such as Terra import a workflow by ID. The test inputs
use paths inside this repository, so they show the shape of the inputs rather than run as they are
on another platform; `scripts/cloud_inputs.py` makes the platform version.

## DRS

On Terra or AnVIL, data is usually referred to by a DRS URI (`drs://…`), which the platform
resolves to a signed URL at run time. Cromwell 91 lists `drs` among its filesystems in
`service-info`, but resolving a URI needs a resolver service set in its configuration (on Terra,
DRSHub), which a local server does not have. Nothing here was run with DRS inputs.

What is in place: `scripts/cloud_inputs.py` keeps any value that already contains `://`, so a
`drs://` URI given with `--set reads_bam=drs://…` reaches the engine unchanged. The workflow
streams the reads and reference from HTTPS URLs by default; with DRS inputs those would be
passed as files instead, as in the HealthOmics example in the [cloud run](results/cloud-run.md).
