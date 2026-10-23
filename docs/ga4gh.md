# GA4GH standards

Migration of these workflows between platforms depends on 3 GA4GH standards. These are WES
(workflow execution through an API), TRS (finding workflows in registries such as Dockstore), and
DRS (referencing data by ID instead of bucket paths). This page describes the work which has and
has not been carried out for each standard.

| Standard | Status here |
|---|---|
| WES 1.0 (Workflow Execution Service) | **Run.** The `fixture` and `ci` profiles ran through a local Cromwell 91 WES server and gave the same metrics as miniwdl |
| TRS 2.0 (Tool Registry Service), through Dockstore | **Ready to register.** `.dockstore.yml` lists the four workflows; publishing needs the Dockstore GitHub App installed on the repository |
| DRS 1.x (Data Repository Service) | **Not run.** Inputs given as `drs://` URIs pass through `scripts/cloud_inputs.py` unchanged; resolving them needs a DRS resolver in the engine's configuration |

## WES: the same workflow through a second engine

WES is the API used by platforms such as Terra and AnVIL to accept workflow execution requests.
A run starts with `POST /runs` containing the workflow URL and its inputs. This is followed by
polling `GET /runs/{id}/status`. `scripts/wes_run.py` uses the Python standard library to
perform this process. Therefore, it works against any WES 1.0 server.

This test is stringent. `make wes` runs the profile through a WES server. It uses
`scripts/compare_metrics.py` to compare the results against those from the same profile in miniwdl
and determine whether the regression gate passes. Since the tool images and parameters are
identical, the regression gate's exact-match rule applies. All true positive counts must match
exactly, and a close match is not sufficient.

| Profile | Engine | WES state | Run time (WES log) | Gate against miniwdl |
|---|---|---|---:|---|
| `fixture` (30 kb, 9 tasks) | Cromwell 91, local Docker backend | COMPLETE | 76 s | [PASS, identical](results/fixture-wes/gate.md) |
| `ci` (200 kb, 10 tasks) | Cromwell 91, local Docker backend | COMPLETE | 105 s | [PASS, identical](results/ci-wes/gate.md) |

Each folder also contains `wes_run.json` which records the run ID and the server's WES and
engine versions. It also records task names, task exit codes, and output names, but includes no
paths on the server.

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

`make wes` rewrites the inputs so that all local files become URLs under `WES_FILES`
(`scripts/cloud_inputs.py --target wes`). It submits `wdl/main.wdl` by URL, and Cromwell
resolves relative import paths against that URL. Then, it waits for completion and writes the
results to `docs/results/<profile>-wes/`. It waits up to 1 hour. For a longer run, set
`WES_TIMEOUT` in seconds.

### What came up

- **Cromwell 92 cannot run digest-pinned images on its local backend.** All tasks failed due to the
  error
  `No coercion defined from '…@sha256:…' of type 'cromwell.backend.validation.Containers' to 'String?'`
  ([broadinstitute/cromwell#7846](https://github.com/broadinstitute/cromwell/issues/7846)). Image tags
  worked, but this workflow pins every image by digest on purpose. Disabling hash lookup in
  Cromwell did not improve the outcome. The same workflow ran unchanged in Cromwell 91. According to
  the issue report, cloud backends were unaffected. The [cloud run](results/cloud-run.md) on GCP
  Batch lists it as a check.
- **Cromwell renames `http://` inputs.** They are saved with hashed file names, and the
  stratification names in the results came from the file names. The workflow now takes the names
  from the input paths before localization (`strat_names` in `wdl/main.wdl`). So both engines
  report `lowmap_or_segdup`, not a hash. The names come from the end of each URL, so each URL must
  end in the file name. A signed URL or a `drs://` ID does not, and the stratum would be named
  after the URL or the ID.
- **Cromwell saves downloaded inputs so that only its own runtime user can read them** (permission
  mode 600). Because the ngs-preflight image ran as an unprivileged user, the `Preflight` task
  could not open its own BED file in Cromwell. However, it could open the file in miniwdl. This
  image now runs as root like most images used in workflows, including those for biocontainers,
  GATK, and DeepVariant. Run by hand, it takes `--user "$(id -u):$(id -g)"` so that reports are
  not owned by root.

## TRS and Dockstore

`.dockstore.yml` in the repository root registers 4 WDL workflows:

| Dockstore name | Descriptor | Test inputs |
|---|---|---|
| `wgs-release-validation` | `wdl/main.wdl` | `inputs/ci.json`, `inputs/fixture.json` |
| `longread-handoff` | `wdl/optional/longread.wdl` | `inputs/longread.json` |
| `sv-merge` | `wdl/optional/sv_merge.wdl` | none (it needs a finished long-read run) |
| `customer-deliverables` | `wdl/optional/deliverables.wdl` | `inputs/deliverables.json` |

To publish, install the Dockstore GitHub App for the repository through dockstore.org. After this,
the corresponding workflow version is updated each time you push to a branch or tag. Dockstore
provides all versions through the TRS API which platforms such as Terra use to import workflows by
ID. Since the test inputs use paths within this repository, they do not run as they are on another
platform. These inputs are used to show the input structure. `scripts/cloud_inputs.py` is used to
create platform-specific inputs.

## DRS

In Terra or AnVIL, data are typically referenced using DRS URIs (`drs://…`) which the platform
resolves to signed URLs at runtime. Cromwell 91 lists `drs` as one of its file systems in
`service-info`. However, URI resolution requires a resolver service to be configured (DRSHub in
Terra), and this configuration was not set on the local server. Nothing was run using DRS inputs
here.

Currently, `scripts/cloud_inputs.py` preserves values which already contain `://`.
Therefore, a `drs://` URI specified through `--set reads_bam=drs://…` is passed to the engine
unchanged. By default, the workflow streams sequencing reads and reference sequences through
HTTPS URLs. For DRS inputs, these data would be passed as files instead in the same way as
the HealthOmics example in [cloud run](results/cloud-run.md).
