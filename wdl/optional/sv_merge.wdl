version 1.0

# Optional SV merging study: combine the pbsv and Sniffles calls from the long-read module in
# different ways and benchmark each result exactly as the single callers are benchmarked.
#   pbsv, sniffles   each caller alone (PASS calls)
#   union            every call from both callers, no de-duplication
#   collapse         the union with near-identical calls merged by `truvari collapse` (its defaults)
#   collapse_loose   the same, but calls are merged at the benchmark's matching thresholds
#   intersect        pbsv calls that Sniffles also made, matched by `truvari bench`
# Inputs are the region-filtered SV VCFs that `make longread` writes (LongRead.sv_vcfs).

import "../tasks/prepare.wdl" as prepare
import "longread.wdl" as lr

workflow SvMerge {
    input {
        String region
        String? ref_url
        File? ref_fasta
        File pbsv_vcf
        File sniffles_vcf
        File truth_vcf            # v5.0q stvar, cut to the region (plain VCF)
        File truth_bed            # v5.0q stvar benchmark regions, cut to the region
        String sample = "HG002"

        String samtools_docker = "quay.io/biocontainers/samtools:1.24--h9dcdb79_1@sha256:a130447589651ed09252aa95a5e4f4132942cdb54d835d81a04a9a930d656561"
        String bcftools_docker = "quay.io/biocontainers/bcftools:1.24--h118bc1c_4@sha256:186c45de3059dbb1837006c27788284c89d17f8e693e7804624b6cf6ca5caca0"
        String truvari_docker = "quay.io/biocontainers/truvari:5.5.0--pyhdfd78af_0@sha256:28a193205760fad402674f6011425cee09f45085ab82d57f5ff3df4bc59c1264"
    }

    String contig = sub(region, ":.*", "")

    call prepare.FetchReference {
        input: ref_url = ref_url, ref_fasta = ref_fasta, contig = contig, docker = samtools_docker
    }
    call lr.PrepareTruth {
        input: vcf = truth_vcf, label = "truth", docker = bcftools_docker
    }
    call Union {
        input: pbsv_vcf = pbsv_vcf, sniffles_vcf = sniffles_vcf, sample = sample, docker = bcftools_docker
    }
    call Collapse {
        input: union_vcf = Union.union_vcf, union_tbi = Union.union_tbi, ref_fasta = FetchReference.fasta,
               ref_fai = FetchReference.fai, docker = truvari_docker
    }
    call lr.SortIndexVcf as SortCollapsed {
        input: vcf = Collapse.vcf, label = "collapse", region = region, docker = bcftools_docker
    }
    call Collapse as CollapseLoose {
        input: union_vcf = Union.union_vcf, union_tbi = Union.union_tbi, ref_fasta = FetchReference.fasta,
               ref_fai = FetchReference.fai, refdist = 2000, pctseq = 0.7, pctsize = 0.7, docker = truvari_docker
    }
    call lr.SortIndexVcf as SortCollapsedLoose {
        input: vcf = CollapseLoose.vcf, label = "collapse_loose", region = region, docker = bcftools_docker
    }
    call Intersect {
        input: pbsv_vcf = Union.pbsv_out, pbsv_tbi = Union.pbsv_tbi, sniffles_vcf = Union.sniffles_out,
               sniffles_tbi = Union.sniffles_tbi, ref_fasta = FetchReference.fasta, ref_fai = FetchReference.fai,
               docker = truvari_docker
    }

    Array[String] labels = ["pbsv", "sniffles", "union", "collapse", "collapse_loose", "intersect"]
    Array[File] vcfs = [Union.pbsv_out, Union.sniffles_out, Union.union_vcf, SortCollapsed.out_vcf,
                        SortCollapsedLoose.out_vcf, Intersect.vcf]
    Array[File] tbis = [Union.pbsv_tbi, Union.sniffles_tbi, Union.union_tbi, SortCollapsed.out_tbi,
                        SortCollapsedLoose.out_tbi, Intersect.tbi]

    scatter (i in range(length(labels))) {
        call lr.Truvari {
            input: truth_vcf = PrepareTruth.out_vcf, truth_tbi = PrepareTruth.out_tbi,
                   query_vcf = vcfs[i], query_tbi = tbis[i], bed = truth_bed,
                   ref_fasta = FetchReference.fasta, ref_fai = FetchReference.fai,
                   label = labels[i], docker = truvari_docker
        }
    }

    call CountRecords {
        input: labels = labels, vcfs = vcfs, docker = bcftools_docker
    }

    output {
        Array[File] summaries = Truvari.summary
        Array[File] refine_summaries = Truvari.refine_summary
        Array[File] resources = Truvari.resources
        File counts = CountRecords.counts
        Array[File] collapse_logs = [Collapse.log, CollapseLoose.log]
    }
}

task Union {
    input {
        File pbsv_vcf
        File sniffles_vcf
        String sample
        String docker
    }

    command <<<
        set -euo pipefail
        # The callers name the sample differently (HG002, SAMPLE); give both the same name so the
        # union is a single-sample VCF. Only PASS calls are used, as in the benchmark.
        echo "~{sample}" > sample.txt
        for c in pbsv:"~{pbsv_vcf}" sniffles:"~{sniffles_vcf}"; do
            bcftools reheader -s sample.txt "${c#*:}" | bcftools view -f PASS -Oz -o "${c%%:*}.vcf.gz"
            bcftools index --tbi "${c%%:*}.vcf.gz"
        done
        bcftools concat -a pbsv.vcf.gz sniffles.vcf.gz -Ou | bcftools sort -Oz -o union.vcf.gz
        bcftools index --tbi union.vcf.gz
    >>>

    output {
        File pbsv_out = "pbsv.vcf.gz"
        File pbsv_tbi = "pbsv.vcf.gz.tbi"
        File sniffles_out = "sniffles.vcf.gz"
        File sniffles_tbi = "sniffles.vcf.gz.tbi"
        File union_vcf = "union.vcf.gz"
        File union_tbi = "union.vcf.gz.tbi"
    }

    runtime {
        docker: docker
        cpu: 1
        memory: "2 GiB"
    }
}

task Collapse {
    input {
        File union_vcf
        File union_tbi
        File ref_fasta
        File ref_fai
        Int refdist = 500         # truvari collapse defaults
        Float pctseq = 0.95
        Float pctsize = 0.95
        String docker
    }

    command <<<
        set -euo pipefail
        ln -s "~{union_vcf}" union.vcf.gz; ln -s "~{union_tbi}" union.vcf.gz.tbi
        ln -s "~{ref_fasta}" ref.fa; ln -s "~{ref_fai}" ref.fa.fai
        # Of each set of matching calls, the first in file order is kept.
        truvari collapse -i union.vcf.gz -o collapse.vcf -c removed.vcf -f ref.fa \
            --refdist ~{refdist} --pctseq ~{pctseq} --pctsize ~{pctsize} 2> collapse.log
    >>>

    output {
        File vcf = "collapse.vcf"
        File removed = "removed.vcf"
        File log = "collapse.log"
    }

    runtime {
        docker: docker
        cpu: 1
        memory: "2 GiB"
    }
}

task Intersect {
    input {
        File pbsv_vcf
        File pbsv_tbi
        File sniffles_vcf
        File sniffles_tbi
        File ref_fasta
        File ref_fai
        String docker
    }

    command <<<
        set -euo pipefail
        ln -s "~{pbsv_vcf}" pbsv.vcf.gz; ln -s "~{pbsv_tbi}" pbsv.vcf.gz.tbi
        ln -s "~{sniffles_vcf}" sniffles.vcf.gz; ln -s "~{sniffles_tbi}" sniffles.vcf.gz.tbi
        ln -s "~{ref_fasta}" ref.fa; ln -s "~{ref_fai}" ref.fa.fai
        # pbsv as the base and Sniffles as the comparison, with the benchmark's distances; the
        # matched base calls (tp-base) are the pbsv calls Sniffles agrees with. Sizes down to 20 bp,
        # pbsv's minimum, and no upper limit, so no pbsv call is dropped before matching.
        truvari bench -b pbsv.vcf.gz -c sniffles.vcf.gz -o agree -f ref.fa --sizemin 20 --sizefilt 20 \
            --sizemax -1 --passonly -r 2000 -C 5000
        cp agree/tp-base.vcf.gz intersect.vcf.gz
        python -c "import pysam; pysam.tabix_index('intersect.vcf.gz', preset='vcf', force=True)"
    >>>

    output {
        File vcf = "intersect.vcf.gz"
        File tbi = "intersect.vcf.gz.tbi"
    }

    runtime {
        docker: docker
        cpu: 1
        memory: "2 GiB"
    }
}

task CountRecords {
    input {
        Array[String] labels
        Array[File] vcfs
        String docker
    }

    command <<<
        set -euo pipefail
        paste ~{write_lines(labels)} ~{write_lines(vcfs)} > pairs.tsv
        printf 'label\trecords\trecords_ge50\n' > counts.tsv
        while IFS=$'\t' read -r label vcf; do
            all=$(bcftools view -H "$vcf" | wc -l)
            big=$(bcftools view -H -i 'abs(INFO/SVLEN)>=50 || strlen(REF)>=51 || strlen(ALT)>=51' "$vcf" | wc -l)
            printf '%s\t%s\t%s\n' "$label" "$all" "$big" >> counts.tsv
        done < pairs.tsv
    >>>

    output {
        File counts = "counts.tsv"
    }

    runtime {
        docker: docker
        cpu: 1
        memory: "1 GiB"
    }
}
