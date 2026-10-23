# Running in the cloud

!!! warning "Not run yet"
    These are the steps for one real cloud run of the `full` profile. They have **not been
    executed**: there is no billed cost below, and the estimate-versus-actual comparison is still
    to do. Every fact below was checked against the provider's documentation or source code on
    2026-10-22. Each step marked *check* is one that only a real run can confirm.

The workflow runs locally with miniwdl. In the cloud it runs on either of these:

| | AWS HealthOmics | GCP Batch through Cromwell 92 |
|---|---|---|
| What you run | Nothing: a managed service | A Cromwell process (a laptop or a small VM) that submits Batch jobs |
| Internet from tasks | **None by default** (runs reach same-region S3 and ECR only) | Yes, unless the VMs are given no external address |
| Images | Private ECR in the same region, x86_64, **no ENTRYPOINT** | Any registry the VMs can reach |
| Spot | No | Yes (`preemptible` above 0) |
| Inputs JSON | Bare input names (`region`, not `ReleaseValidation.region`) | Same as miniwdl |

`scripts/cloud_inputs.py` turns an inputs file such as `inputs/full.json` into one for either
target, and lists the local files that have to be uploaded first.

## Step 0: a budget alert, before anything else

A budget alert sends an email when spending crosses a threshold. It does not stop spending. Set
one at a few dollars before creating any resource; the `full` profile should cost cents.

```bash
# AWS: monthly cost budget of 10 USD, email at 50 % and 100 % of actual spend
aws budgets create-budget --account-id "$AWS_ACCOUNT_ID" \
    --budget '{"BudgetName":"wrv","BudgetLimit":{"Amount":"10","Unit":"USD"},"TimeUnit":"MONTHLY","BudgetType":"COST"}' \
    --notifications-with-subscribers '[
      {"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":50},
       "Subscribers":[{"SubscriptionType":"EMAIL","Address":"you@example.org"}]},
      {"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":100},
       "Subscribers":[{"SubscriptionType":"EMAIL","Address":"you@example.org"}]}]'

# GCP
gcloud billing budgets create --billing-account="$BILLING_ACCOUNT" --display-name=wrv \
    --budget-amount=10USD --threshold-rule=percent=0.5 --threshold-rule=percent=1.0
```

Keep account IDs, project IDs and bucket names in environment variables or in git-ignored files
(`cromwell-gcp.conf`, `cloud/*.env`, `_cloud/`). Never commit credentials.

## Option 1: AWS HealthOmics

### 1. Stage the inputs in S3

Runs have no internet access unless you set up VPC networking (a NAT gateway in your VPC, chosen
per run with `networkingMode`). The simpler route is to stage everything in S3. The run then
uses the local-file inputs (`ref_fasta`, `reads_bam`) instead of the streaming ones (`ref_url`,
`reads_url`):

```bash
make full                                   # the local run leaves results/full/slice.bam(.bai)
samtools faidx https://storage.googleapis.com/deepvariant/case-study-testdata/GCA_000001405.15_GRCh38_no_alt_analysis_set.fa \
    chr20 > data/chr20.fa                   # FetchReference indexes it in the run

# run this after step 2, adding --set <name>_docker=<ECR URI> for each of the eight images
python scripts/cloud_inputs.py inputs/full.json --target healthomics --prefix "s3://$BUCKET/wrv" \
    --drop ref_url --drop reads_url \
    --set ref_fasta=data/chr20.fa \
    --set reads_bam=results/full/slice.bam --set reads_bai=results/full/slice.bam.bai \
    --out _cloud/full.healthomics.json --uploads _cloud/uploads.tsv

while IFS=$'\t' read -r local remote; do aws s3 cp "$local" "$remote"; done < _cloud/uploads.tsv
```

`cloud_inputs.py` refuses to write a HealthOmics file that still has an `https://` input, and
says which input it is. The slice already has 1 kb of padding and a chr20-only header, so
FetchReadsSlice cuts it again without changing it.

### 2. Put every image in private ECR

HealthOmics pulls images only from private ECR in the region of the run. Two more requirements
come from its documentation: images must be x86_64 (all eight are amd64), and they must not set
an ENTRYPOINT, because the engine injects each task's command as a bash script. Four of the
eight images set one: the biocontainers samtools, bcftools and mosdepth images, and
happy-vcfeval, which is built on a biocontainer. All four use `/usr/local/env-execute`.
`cloud/no-entrypoint.Dockerfile` clears it and changes nothing else. It was tested on samtools
and happy-vcfeval: both tools run from the rebuilt images.

```bash
ECR="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
aws ecr get-login-password | docker login --username AWS --password-stdin "$ECR"

# images with an ENTRYPOINT: rebuild without it, then push
for pair in \
    samtools=quay.io/biocontainers/samtools:1.24--h9dcdb79_1@sha256:a130447589651ed09252aa95a5e4f4132942cdb54d835d81a04a9a930d656561 \
    bcftools=quay.io/biocontainers/bcftools:1.24--h118bc1c_4@sha256:186c45de3059dbb1837006c27788284c89d17f8e693e7804624b6cf6ca5caca0 \
    mosdepth=quay.io/biocontainers/mosdepth:0.3.14--h87be163_2@sha256:63f50e21185f5ce50fb0b6c6d3b3d4b7e50ab19356096f1045ca2538b739793c \
    happy-vcfeval=happy-vcfeval:0.3.15-rtg3.13; do
  name=${pair%%=*}; base=${pair#*=}
  aws ecr create-repository --repository-name "wrv/$name" >/dev/null
  docker build -f cloud/no-entrypoint.Dockerfile --build-arg BASE="$base" -t "$ECR/wrv/$name:cloud" cloud
  docker push "$ECR/wrv/$name:cloud"        # prints the digest to pin in the inputs
done
# images without one: retag and push (or use an ECR pull-through cache rule for Docker Hub)
#   broadinstitute/gatk, google/deepvariant, python:3.12-slim, ngs-preflight:0.1.0
```

Then pass each pushed image to `cloud_inputs.py` by digest, for example
`--set samtools_docker=$ECR/wrv/samtools@sha256:...`. A run is then fully pinned, and no
registry mapping is needed: HealthOmics needs no mapping for images given by private ECR URI.
Each repository also needs a policy that lets the `omics.amazonaws.com` service principal pull
(`ecr:BatchGetImage`, `ecr:GetDownloadUrlForLayer`). See "Policies for Amazon ECR" in the
HealthOmics guide. *Check*: the rebuilt images are new digests, so record them in the run notes
next to the upstream digests in `wdl/main.wdl`.

### 3. Create the workflow and start the run

```bash
(cd wdl && zip -r ../_cloud/workflow.zip main.wdl tasks)
aws omics create-workflow --name wgs-release-validation --engine WDL \
    --definition-zip fileb://_cloud/workflow.zip --main main.wdl
# parameter descriptions come from parameter_meta; inputs with defaults are optional
aws omics get-workflow --id "$WORKFLOW_ID"          # wait for status ACTIVE

aws omics start-run --workflow-id "$WORKFLOW_ID" --role-arn "$OMICS_ROLE_ARN" \
    --name full-$(date +%Y%m%d) --parameters file://_cloud/full.healthomics.json \
    --output-uri "s3://$BUCKET/wrv/runs/" --storage-type DYNAMIC
aws omics get-run --id "$RUN_ID"; aws omics list-run-tasks --id "$RUN_ID"
```

The role needs a trust policy for `omics.amazonaws.com`, read access to the input prefix,
write access to the output prefix, ECR pull and CloudWatch Logs. Use `DYNAMIC` run storage:
with `STATIC`, a fixed minimum is billed for the whole run however little the tasks use. That
minimum is assumed to be 1,200 GiB in `config/prices.yaml`, which is enough to dominate a run
this small.

Known differences from the local run:

- `/tmp` is replaced by a shared run filesystem. No task here writes to `/tmp`; DeepVariant's
  intermediate files go to `tmp/` in the task directory.
- Task storage (`disks:`) is ignored; dynamic run storage covers all tasks.
- HealthOmics retries a task that fails for a service reason up to two times. The DeepVariant
  out-of-memory guard ([CS-03](../case-studies/CS-03-deepvariant-memory.md)) fails the task on
  a real OOM, so that failure is reported, not retried.
- *Check*: `resources.json` reads `/sys/fs/cgroup`. If HealthOmics tasks do not expose cgroup v2
  there, CPU and memory are recorded as -1 and the per-task cost has to come from the run
  manifest instead.

## Option 2: GCP Batch through Cromwell 92

### 1. Project, service account and bucket

```bash
gcloud services enable batch.googleapis.com compute.googleapis.com logging.googleapis.com \
    storage.googleapis.com artifactregistry.googleapis.com
gcloud storage buckets create "gs://$BUCKET" --location=northamerica-northeast1
```

The VM service account needs `roles/batch.agentReporter`, `roles/logging.logWriter`, object
access on the bucket and `roles/artifactregistry.reader`. The account that runs Cromwell needs
`roles/batch.jobsEditor` and `roles/iam.serviceAccountUser` on the VM account. Authenticate
Cromwell with `gcloud auth application-default login`.

### 2. Images

Public images (Docker Hub, quay.io) need no setup. Push the two locally built ones,
`happy-vcfeval` and `ngs-preflight`, to Artifact Registry, and pass them as
`--set happy_docker=...` and `--set preflight_docker=...`. Batch does not care about the
ENTRYPOINT, so no rebuild is needed.

### 3. Configure and run

```bash
cp cloud/cromwell-gcp.example.conf cromwell-gcp.conf      # git-ignored; fill in the <...> values
python scripts/cloud_inputs.py inputs/full.json --target cromwell --prefix "gs://$BUCKET/wrv" \
    --set happy_docker=... --set preflight_docker=... \
    --out _cloud/full.cromwell.json --uploads _cloud/uploads.tsv
while IFS=$'\t' read -r local remote; do gcloud storage cp "$local" "$remote"; done < _cloud/uploads.tsv

(cd wdl && zip -r ../_cloud/imports.zip tasks)
java -Dconfig.file=cromwell-gcp.conf -jar cromwell-92.jar run wdl/main.wdl \
    --inputs _cloud/full.cromwell.json --imports _cloud/imports.zip \
    --metadata-output _cloud/full.metadata.json
```

The Cromwell inputs keep the streaming URLs: Batch VMs have external addresses
(`noAddress: false`) and read the reference and reads over HTTPS, as the local run does.

On Spot: the Cromwell documentation page for Batch does not mention Spot. In the Cromwell
source, any `preemptible` value above 0 sets the Batch provisioning model to `SPOT`
(`BatchUtilityConversions.toProvisioningModel`). The example config sets `preemptible: 2` as a
default for every task. *Check*: a preempted task should be retried, and should fall back to a
standard VM after the retries; confirm this in the run metadata.

On Cromwell versions: Cromwell 92's local backend fails on images pinned by digest
([cromwell#7846](https://github.com/broadinstitute/cromwell/issues/7846)), and the
[WES run](../ga4gh.md) used Cromwell 91 for that reason. The issue reports the cloud backends as
unaffected. *Check*: the first Batch task starts with its `@sha256:` image; if it fails with
"No coercion defined", use Cromwell 91.

## Reading the cost, and comparing it with the estimate

- **What to compare.** The per-task cost of the `full` profile from the run's own records, set
  against what `scripts/estimate_cost.py` predicts for the same profile from the local
  `resources.tsv` and `config/prices.yaml`
  ([cost estimate](cost-estimate.md)). The 30x WGS extrapolation cannot be checked this way;
  only the per-region prices and the machine choice can.
- **AWS.** Billing data lags by up to a day. Use Cost Explorer filtered to the HealthOmics
  service (or `aws ce get-cost-and-usage`) for the billed amount, and `list-run-tasks` for each
  task's instance type and duration.
- **GCP.** Label the VMs (Cromwell's `google_labels` workflow option) and filter the billing
  export or the Billing reports page by that label. Cromwell's metadata has each task's machine
  type and duration.
- **Where the gap will come from.** The estimate prices task CPU time at the cheapest listed
  machine. A real run adds VM boot and image-pull time for each task, a minimum billing
  increment, and storage. With tasks of a few minutes each, that overhead can be as large as
  the compute.

Record the run date, region, image digests, billed cost and the estimate in this page when the
run is done, and delete the budget, the workflow and the buckets afterwards.
