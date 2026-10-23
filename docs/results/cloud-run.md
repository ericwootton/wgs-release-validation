# Running in the cloud

!!! warning "Not run yet"
    These are the steps for one real cloud run of the `full` profile. These steps have
    **not been executed**. No billed costs are reported below, and the comparison between estimated
    and actual costs remains to be done. All facts below were verified against provider
    documentation or source code on 2026-10-22. Steps marked *check* can only be confirmed after
    they have actually been executed.

This workflow is run locally using miniwdl. It is run in the cloud using any of the following methods:

| | AWS HealthOmics | GCP Batch through Cromwell 92 |
|---|---|---|
| What you run | Nothing: a managed service | A Cromwell process (a laptop or a small VM) that submits Batch jobs |
| Internet from tasks | **None by default** (runs reach same-region S3 and ECR only) | Yes, unless the VMs are given no external address |
| Images | Private ECR in the same region, x86_64, **no ENTRYPOINT** | Any registry the VMs can reach |
| Spot | No | Yes (`preemptible` above 0) |
| Inputs JSON | Bare input names (`region`, not `ReleaseValidation.region`) | Same as miniwdl |

`scripts/cloud_inputs.py` converts input files such as `inputs/full.json` into inputs for one
of 2 targets and lists local files which must be uploaded in advance.

## Step 0: a budget alert, before anything else

Budget alerts send emails when spending exceeds the threshold. They do not stop spending.
Before creating resources, set a budget alert with a threshold of a few dollars. Costs for the
`full` profile should be only cents.

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

Store account IDs, project IDs, and bucket names in environment variables or files designated
to be ignored by git (`cromwell-gcp.conf`, `cloud/*.env`, `_cloud/`). Never commit credentials.

## Option 1: AWS HealthOmics

### 1. Stage the inputs in S3

Unless VPC networking is configured, the runtime environment has no internet access. This
requires a NAT gateway within the VPC and selection through `networkingMode` for each run. A
simpler approach is to store everything in S3 in advance. In this case, local file inputs
(`ref_fasta`, `reads_bam`) are used at runtime instead of streaming inputs (`ref_url`,
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

`cloud_inputs.py` refuses to write HealthOmics files which still contain `https://` inputs
and identifies the specific inputs involved. Since the slice already includes 1 kb of padding
and a chr20-only header, FetchReadsSlice cuts it again without changing it.

### 2. Put every image in private ECR

HealthOmics only pulls images from private ECR repositories in the execution region. Its
documentation also lists 2 requirements. Images must use the x86_64 architecture (all 8 images
are amd64), and ENTRYPOINT must not be set. This is because the engine inserts each task's
commands as a bash script. Among the 8 images, 4 set one. These were the
biocontainers samtools, bcftools, and mosdepth images, and happy-vcfeval which was built from a
biocontainer. These 4 images all use `/usr/local/env-execute`. `cloud/no-entrypoint.Dockerfile`
removes this setting and changes nothing else. Tests using samtools and happy-vcfeval showed
that these 2 tools were able to run in the rebuilt images.

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

Next, pass each pushed image to `cloud_inputs.py` by specifying its digest. For example, use
`--set samtools_docker=$ECR/wrv/samtools@sha256:...`. This keeps the run fully pinned, and no
registry mapping is needed. Images specified using private ECR URIs in HealthOmics require no
mapping. Each repository also needs a policy that lets the
`omics.amazonaws.com` service principal pull images (`ecr:BatchGetImage`,
`ecr:GetDownloadUrlForLayer`). See Policies for Amazon ECR in the HealthOmics guide. *Check*:
rebuilt images have new digests, so record them alongside the upstream digests listed in
`wdl/main.wdl` in the run notes.

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

This role requires a trust policy for `omics.amazonaws.com`. It also requires read access to
the input prefix, write access to the output prefix, permission to pull from ECR, and access
to CloudWatch Logs. Set run storage to `DYNAMIC`. When `STATIC` is used, a fixed minimum
capacity is billed throughout the run regardless of how little storage the tasks actually
use. This minimum capacity is assumed to be 1,200 GiB in `config/prices.yaml`. For a run this
small, this minimum is enough to dominate the cost.

Known differences from local execution:

- `/tmp` is replaced by the shared filesystem used for execution. No task here writes to
  `/tmp`. Intermediate files from DeepVariant go to `tmp/` within the task directory.
- Task storage (`disks:`) is ignored, and dynamic execution storage is applied to all tasks.
- HealthOmics retries tasks which fail for service-side reasons up to two times. DeepVariant's
  out-of-memory guard ([CS-03](../case-studies/CS-03-deepvariant-memory.md)) fails the task
  when an OOM actually occurs. Therefore, this failure is reported and is not retried.
- *Check*: `resources.json` reads `/sys/fs/cgroup`. If a HealthOmics task does not expose cgroup
  v2 at this location, CPU and memory will be recorded as -1. In that case, the cost of each
  task must be obtained from the execution manifest instead.

## Option 2: GCP Batch through Cromwell 92

### 1. Project, service account and bucket

```bash
gcloud services enable batch.googleapis.com compute.googleapis.com logging.googleapis.com \
    storage.googleapis.com artifactregistry.googleapis.com
gcloud storage buckets create "gs://$BUCKET" --location=northamerica-northeast1
```

The VM service account requires `roles/batch.agentReporter`, `roles/logging.logWriter`, access
to objects in the bucket, and `roles/artifactregistry.reader`. To run Cromwell, the account
requires `roles/batch.jobsEditor` and `roles/iam.serviceAccountUser` on the VM service
account. Use `gcloud auth application-default login` to authenticate Cromwell.

### 2. Images

Public images (Docker Hub, quay.io) require no setup. Push the two locally built images
`happy-vcfeval` and `ngs-preflight` to Artifact Registry. Then, specify them using
`--set happy_docker=...` and `--set preflight_docker=...`, respectively. Since Batch
does not care about ENTRYPOINT, no rebuild is required.

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

Streaming URLs are kept in the Cromwell inputs. Batch VMs have external
addresses (`noAddress: false`). They read the reference sequence and
sequencing reads over HTTPS in the same way as during local execution.

The Cromwell documentation page for Batch does not mention Spot. In the Cromwell source code,
the Batch provisioning model is set to `SPOT` when `preemptible` is greater than 0
(`BatchUtilityConversions.toProvisioningModel`). The configuration example sets
`preemptible: 2` as the default for all tasks. *Check*: a preempted task should be retried, and should fall back to a
standard VM after the retries. Confirm this in the run metadata.

The [WES run](../ga4gh.md) used Cromwell 91 because the Cromwell 92 local backend fails when
using images pinned by digest
([cromwell#7846](https://github.com/broadinstitute/cromwell/issues/7846)). The issue report
states that cloud backends are unaffected. *Check* that the first Batch task starts using the
`@sha256:` image. If it fails with a “No coercion defined” error, use Cromwell 91.

## Reading the cost, and comparing it with the estimate

- **What to compare.** For the `full` profile, task costs derived from this run's records will
  be compared with values predicted by `scripts/estimate_cost.py`. These predictions use the
  local `resources.tsv` and `config/prices.yaml` for the same profile
  ([cost estimate](cost-estimate.md)). This method cannot validate extrapolation to 30x WGS
  and can only validate prices and machine selection in each region.
- **AWS.** Billing data updates can be delayed by up to 1 day. Use Cost Explorer filtered to
  the HealthOmics service (or `aws ce get-cost-and-usage`) to verify the billed amount. Then,
  use `list-run-tasks` to verify the instance type and runtime for each task.
- **GCP.** Add a label to the VM (Cromwell workflow option `google_labels`), and use it to
  filter exported billing data or the billing report page. Cromwell metadata includes the
  machine type and runtime for each task.
- **Where the gap will come from.** This estimate uses the cheapest listed machine's rate
  for the CPU time of each task. During actual runs, minimum billing units and storage also
  incur costs in addition to VM startup and image retrieval for each task. When each task
  takes a few minutes, this overhead can cost as much as the compute.

After the run is complete, record the run date, region, image digests, billed amount, and
estimated amount on this page. Then, delete the budget, workflow, and buckets.
