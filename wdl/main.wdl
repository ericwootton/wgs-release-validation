version 1.0

# ReleaseValidation: call small variants on a region of GIAB HG002, benchmark the calls against
# the GIAB truth set with stratified metrics, and summarise them for the regression gate
# (scripts/compare_metrics.py).
#
# Container images are pinned by digest. The tag is kept in front of the digest for readability;
# Docker ignores it when a digest is present. Override any image from the inputs JSON to test an
# upgrade (see inputs/upgrade_*.json).

import "tasks/prepare.wdl" as prepare
import "tasks/call.wdl" as calling
import "tasks/qc.wdl" as qc
import "tasks/benchmark.wdl" as benchmark
import "tasks/report.wdl" as report

workflow ReleaseValidation {
    input {
        String run_label
        String region                       # e.g. chr20:21800001-22000000 (1-based, inclusive)
        Array[String] callers = ["gatk"]    # any of "gatk", "deepvariant"

        # Reference and reads: a remote URL (streamed by region) or local files.
        String? ref_url
        File? ref_fasta
        String? reads_url
        File? reads_bam
        File? reads_bai

        # Truth and strata, already cut to the region by scripts/fetch_data.py prepare.
        File truth_vcf
        String truth_set_name = "GIAB v4.2.1 (GRCh38)"   # shown in the report and metrics.json
        File confident_bed
        File region_bed
        Array[File] strat_beds
        File summarize_script

        String extra_norm_args = ""         # only for exercising the regression gate (INC-01)
        String gatk_extra_args = ""         # likewise; e.g. a proposed change to HaplotypeCaller defaults
        Boolean run_preflight = false       # check inputs with ngs-preflight first (image built from that repo)

        String samtools_docker = "quay.io/biocontainers/samtools:1.24--h9dcdb79_1@sha256:a130447589651ed09252aa95a5e4f4132942cdb54d835d81a04a9a930d656561"
        String bcftools_docker = "quay.io/biocontainers/bcftools:1.24--h118bc1c_4@sha256:186c45de3059dbb1837006c27788284c89d17f8e693e7804624b6cf6ca5caca0"
        String gatk_docker = "broadinstitute/gatk:4.7.0.0@sha256:7da5cf586e1c463f0c72908f9ac7dec8c29e37912c82d6e7b3c250f27fcb3891"
        String deepvariant_docker = "google/deepvariant:1.10.0@sha256:962e5a83b1d76aae6990625d47102785f791603f2138aa1fa9aa4fb6a2eecbe6"
        String mosdepth_docker = "quay.io/biocontainers/mosdepth:0.3.14--h87be163_2@sha256:63f50e21185f5ce50fb0b6c6d3b3d4b7e50ab19356096f1045ca2538b739793c"
        String happy_docker = "happy-vcfeval:0.3.15-rtg3.13"   # built from docker/happy-vcfeval
        String preflight_docker = "ngs-preflight:0.1.0"            # built from github.com/ericwootton/ngs-preflight
        String python_docker = "python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704"

        Int deepvariant_shards = 4
        Int deepvariant_memory_gb = 8   # memory grows with shards; measured sizes in docs/case-studies/CS-03
        Int gatk_memory_gb = 6
    }

    String contig = sub(region, ":.*", "")
    # Stratum names come from the input file names, taken here, before localization: Cromwell
    # saves http:// inputs under hashed names, which would otherwise become the stratum names. A
    # URL must therefore end in the file name: a signed URL or a drs:// ID would name the stratum.
    scatter (bed in strat_beds) {
        String strat_name = basename(bed, ".bed")
    }

    call prepare.FetchReference {
        input:
            ref_url = ref_url,
            ref_fasta = ref_fasta,
            contig = contig,
            docker = samtools_docker
    }

    call prepare.FetchReadsSlice {
        input:
            reads_url = reads_url,
            reads_bam = reads_bam,
            reads_bai = reads_bai,
            region = region,
            contig = contig,
            docker = samtools_docker
    }

    if (run_preflight) {
        call prepare.Preflight {
            input:
                ref_fai = FetchReference.fai,
                region_bed = region_bed,
                confident_bed = confident_bed,
                bam = FetchReadsSlice.bam,
                docker = preflight_docker
        }
    }

    call qc.Mosdepth {
        input:
            bam = FetchReadsSlice.bam,
            bai = FetchReadsSlice.bai,
            region_bed = region_bed,
            docker = mosdepth_docker
    }

    call benchmark.NormalizeVcf as NormalizeTruth {
        input:
            vcf = truth_vcf,
            ref_fasta = FetchReference.fasta,
            ref_fai = FetchReference.fai,
            label = "truth",
            docker = bcftools_docker
    }

    scatter (caller in callers) {
        if (caller == "gatk") {
            call calling.HaplotypeCaller {
                input:
                    ref_fasta = FetchReference.fasta,
                    ref_fai = FetchReference.fai,
                    ref_dict = FetchReference.dict,
                    bam = FetchReadsSlice.bam,
                    bai = FetchReadsSlice.bai,
                    region = region,
                    docker = gatk_docker,
                    extra_args = gatk_extra_args,
                    after_preflight = Preflight.report_md,
                    memory_gb = gatk_memory_gb
            }
        }
        if (caller == "deepvariant") {
            call calling.DeepVariant {
                input:
                    ref_fasta = FetchReference.fasta,
                    ref_fai = FetchReference.fai,
                    bam = FetchReadsSlice.bam,
                    bai = FetchReadsSlice.bai,
                    region = region,
                    docker = deepvariant_docker,
                    shards = deepvariant_shards,
                    after_preflight = Preflight.report_md,
                    memory_gb = deepvariant_memory_gb
            }
        }
        File raw_vcf = select_first([HaplotypeCaller.vcf, DeepVariant.vcf])
        File caller_resources = select_first([HaplotypeCaller.resources, DeepVariant.resources])

        call benchmark.NormalizeVcf as NormalizeQuery {
            input:
                vcf = raw_vcf,
                ref_fasta = FetchReference.fasta,
                ref_fai = FetchReference.fai,
                label = caller,
                extra_norm_args = extra_norm_args,
                docker = bcftools_docker
        }

        call qc.VariantQC {
            input:
                vcf = NormalizeQuery.norm_vcf,
                tbi = NormalizeQuery.norm_tbi,
                ref_fasta = FetchReference.fasta,
                ref_fai = FetchReference.fai,
                label = caller,
                docker = bcftools_docker
        }

        call benchmark.HappyBenchmark {
            input:
                truth_vcf = NormalizeTruth.norm_vcf,
                truth_tbi = NormalizeTruth.norm_tbi,
                query_vcf = NormalizeQuery.norm_vcf,
                query_tbi = NormalizeQuery.norm_tbi,
                confident_bed = confident_bed,
                ref_fasta = FetchReference.fasta,
                ref_fai = FetchReference.fai,
                strat_beds = strat_beds,
                strat_names = strat_name,
                label = caller,
                docker = happy_docker
        }
    }

    call report.SummarizeMetrics {
        input:
            extended_csvs = HappyBenchmark.extended_csv,
            labels = callers,
            summarize_script = summarize_script,
            mosdepth_summary = Mosdepth.summary,
            run_label = run_label,
            region = region,
            truth_set = truth_set_name,
            tool_versions = [
                "samtools=" + samtools_docker,
                "bcftools=" + bcftools_docker,
                "gatk=" + gatk_docker,
                "deepvariant=" + deepvariant_docker,
                "mosdepth=" + mosdepth_docker,
                "hap.py=" + happy_docker,
                # Parameters that change calls count as part of the tool set: the gate then
                # attributes a difference to them rather than to non-determinism.
                "gatk_args=" + gatk_extra_args,
                "norm_args=" + extra_norm_args
            ],
            docker = python_docker
    }

    output {
        File metrics_json = SummarizeMetrics.metrics_json
        File metrics_md = SummarizeMetrics.metrics_md
        Array[File] calls_vcf = NormalizeQuery.norm_vcf
        Array[File] calls_tbi = NormalizeQuery.norm_tbi
        Array[File] happy_summary = HappyBenchmark.summary_csv
        Array[File] happy_extended = HappyBenchmark.extended_csv
        Array[File] happy_vcf = HappyBenchmark.annotated_vcf
        Array[File] happy_tbi = HappyBenchmark.annotated_tbi
        Array[File] bcftools_stats = VariantQC.stats
        File coverage_summary = Mosdepth.summary
        File coverage_thresholds = Mosdepth.thresholds
        File slice_bam = FetchReadsSlice.bam
        File slice_bai = FetchReadsSlice.bai
        Int slice_read_count = FetchReadsSlice.read_count
        File? preflight_report = Preflight.report_md
        Array[File] resources = flatten([
            [FetchReference.resources, FetchReadsSlice.resources, Mosdepth.resources,
             NormalizeTruth.resources, SummarizeMetrics.resources],
            caller_resources, NormalizeQuery.resources, VariantQC.resources, HappyBenchmark.resources,
            select_all([Preflight.resources])
        ])
    }

    parameter_meta {
        region: "Region to analyse, samtools style. The reference is cut to this contig and the reads to this region plus 1 kb padding."
        callers: "Variant callers to run and benchmark: gatk (HaplotypeCaller) and/or deepvariant."
        truth_vcf: "GIAB truth VCF cut to the region (scripts/fetch_data.py prepare)."
        truth_set_name: "Name of the truth set, recorded in the report (e.g. GIAB v5.0q smvar)."
        confident_bed: "GIAB benchmark regions intersected with the region."
        strat_beds: "GIAB stratification BEDs cut to the region; each file's basename names the stratum."
        extra_norm_args: "Extra bcftools norm arguments for the query callset. Used only to demonstrate the regression gate catching a bad change."
        gatk_extra_args: "Extra HaplotypeCaller arguments, for trying a proposed parameter change against the baseline."
    }
}
