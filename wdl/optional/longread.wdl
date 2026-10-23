version 1.0

# Optional long-read module (spec §2.14): PacBio HiFi HG002 over one chr20 region.
#   SVs          pbsv and Sniffles2, each benchmarked with truvari against GIAB v5.0q (draft) stvar
#   repeats      TRGT genotypes for the catalogue loci inside the region
#   methylation  pb-CpG-tools CpG scores (needs MM/ML tags, present in the GIAB Revio BAM)
#   handoff      bgzipped + indexed outputs, MANIFEST.tsv, DATA_DICTIONARY.md, QC_SUMMARY.md, VERSIONS.md
#
# The GIAB Revio BAM is aligned to GRCh38-GIABv3 (the no-alt analysis set with decoys and three masked
# genes on chr7 and chr17). chr20 is byte-identical to the NCBI no-alt analysis set used by the
# short-read workflow, so the same chr20 reference is used here.

import "../tasks/prepare.wdl" as prepare

workflow LongRead {
    input {
        String run_label = "longread"
        String region
        String? ref_url
        File? ref_fasta
        String reads_url
        File truth_vcf            # v5.0q stvar, cut to the region (plain VCF)
        File truth_bed            # v5.0q stvar benchmark regions, cut to the region
        File trf_bed              # tandem repeats for pbsv / Sniffles, cut to the region
        Array[File] repeat_catalogs   # TRGT catalogues, records fully inside the region
        File handoff_script       # scripts/longread_handoff.py
        File? cpg_islands         # CpG islands cut to the region, for the island vs open-sea check
        String karyotype = "XY"
        Array[String] plot_loci = ["SCA36_NOP56", "CJD_PRNP"]   # TRGT loci to plot read by read

        String samtools_docker = "quay.io/biocontainers/samtools:1.24--h9dcdb79_1@sha256:a130447589651ed09252aa95a5e4f4132942cdb54d835d81a04a9a930d656561"
        String bcftools_docker = "quay.io/biocontainers/bcftools:1.24--h118bc1c_4@sha256:186c45de3059dbb1837006c27788284c89d17f8e693e7804624b6cf6ca5caca0"
        String pbsv_docker = "quay.io/biocontainers/pbsv:2.11.0--h9ee0642_0@sha256:1a738d93598c14adee41f988bb47705b738798c398250741d074caf78628fd7c"
        String sniffles_docker = "quay.io/biocontainers/sniffles:2.8.0--pyhdfd78af_1@sha256:787139b7592c244e2eb913c486491157e2f5b3a3494df3f7ea0c5876b72058b7"
        String truvari_docker = "quay.io/biocontainers/truvari:5.5.0--pyhdfd78af_0@sha256:28a193205760fad402674f6011425cee09f45085ab82d57f5ff3df4bc59c1264"
        String trgt_docker = "quay.io/biocontainers/trgt:5.1.0--h9ee0642_0@sha256:5fae265afdca9864e5f2d42fbc0da744fe73d0e6a2e472dda506d7d604394b0a"
        String cpg_docker = "quay.io/biocontainers/pb-cpg-tools:3.0.0--h9ee0642_0@sha256:c7d4f999b747e4d5c356669086b929e6eda34249d3e8752ede100cb45faaefb4"
        String python_docker = "python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704"
    }

    String contig = sub(region, ":.*", "")

    call prepare.FetchReference {
        input: ref_url = ref_url, ref_fasta = ref_fasta, contig = contig, docker = samtools_docker
    }
    call prepare.FetchReadsSlice {
        input: reads_url = reads_url, region = region, contig = contig, pad = 20000, docker = samtools_docker,
               memory_gb = 4
    }
    call PrepareTruth {
        input: vcf = truth_vcf, label = "truth", docker = bcftools_docker
    }

    call Pbsv {
        input: bam = FetchReadsSlice.bam, bai = FetchReadsSlice.bai, ref_fasta = FetchReference.fasta,
               ref_fai = FetchReference.fai, region = region, trf_bed = trf_bed, docker = pbsv_docker
    }
    call Sniffles {
        input: bam = FetchReadsSlice.bam, bai = FetchReadsSlice.bai, ref_fasta = FetchReference.fasta,
               ref_fai = FetchReference.fai, trf_bed = trf_bed, docker = sniffles_docker
    }

    Array[Pair[String, File]] sv_calls = [("pbsv", Pbsv.vcf), ("sniffles", Sniffles.vcf)]
    scatter (sv in sv_calls) {
        call SortIndexVcf {
            input: vcf = sv.right, label = sv.left, region = region, docker = bcftools_docker
        }
        call Truvari {
            input: truth_vcf = PrepareTruth.out_vcf, truth_tbi = PrepareTruth.out_tbi,
                   query_vcf = SortIndexVcf.out_vcf, query_tbi = SortIndexVcf.out_tbi,
                   bed = truth_bed, ref_fasta = FetchReference.fasta, ref_fai = FetchReference.fai,
                   label = sv.left, docker = truvari_docker
        }
    }

    call Trgt {
        input: bam = FetchReadsSlice.bam, bai = FetchReadsSlice.bai, ref_fasta = FetchReference.fasta,
               ref_fai = FetchReference.fai, catalogs = repeat_catalogs, karyotype = karyotype, docker = trgt_docker
    }
    call SortIndexVcf as SortTrgt {
        input: vcf = Trgt.vcf, label = "trgt", region = region, docker = bcftools_docker
    }
    call SortIndexBam as SortSpanning {
        input: bam = Trgt.spanning_bam, docker = samtools_docker
    }
    call TrgtPlot {
        input: spanning_bam = SortSpanning.sorted_bam, spanning_bai = SortSpanning.sorted_bai,
               vcf = SortTrgt.out_vcf, tbi = SortTrgt.out_tbi, repeats = Trgt.repeats,
               ref_fasta = FetchReference.fasta, ref_fai = FetchReference.fai, loci = plot_loci,
               docker = trgt_docker
    }
    call CpgScores {
        input: bam = FetchReadsSlice.bam, bai = FetchReadsSlice.bai, ref_fasta = FetchReference.fasta,
               ref_fai = FetchReference.fai, docker = cpg_docker
    }

    call Handoff {
        input:
            run_label = run_label,
            region = region,
            script = handoff_script,
            sv_vcfs = SortIndexVcf.out_vcf,
            sv_tbis = SortIndexVcf.out_tbi,
            truvari_summaries = Truvari.summary,
            truvari_refined = Truvari.refine_summary,
            trgt_vcf = SortTrgt.out_vcf,
            trgt_tbi = SortTrgt.out_tbi,
            trgt_plots = TrgtPlot.plots,
            highlight = plot_loci,
            cpg_bed = CpgScores.combined_bed,
            cpg_tbi = CpgScores.combined_tbi,
            cpg_haplotype_beds = CpgScores.haplotype_beds,
            cpg_haplotype_tbis = CpgScores.haplotype_tbis,
            cpg_islands = cpg_islands,
            read_count = FetchReadsSlice.read_count,
            resources = flatten([
                [FetchReference.resources, FetchReadsSlice.resources, Pbsv.resources, Sniffles.resources,
                 Trgt.resources, CpgScores.resources],
                Truvari.resources
            ]),
            docker = python_docker
    }

    output {
        File handoff_tar = Handoff.tarball
        File qc_summary = Handoff.qc_summary
        File qc_json = Handoff.qc_json
        Array[File] sv_vcfs = SortIndexVcf.out_vcf
        Array[File] truvari_summaries = Truvari.summary
        File trgt_vcf = SortTrgt.out_vcf
        File cpg_bed = CpgScores.combined_bed
        File reads_bam = FetchReadsSlice.bam
    }

    parameter_meta {
        reads_url: "Aligned HiFi BAM with .bai alongside, e.g. the GIAB HG002 Revio 48x GRCh38-GIABv3 BAM."
        truth_vcf: "GIAB HG002 v5.0q stvar VCF cut to the region (fetch_data.py subset stvar_vcf)."
        repeat_catalogs: "TRGT repeat definitions (ID=;MOTIFS=;STRUC=), only loci fully inside the region."
    }
}

task PrepareTruth {
    input {
        File vcf
        String label
        String docker
    }

    command <<<
        set -euo pipefail
        # Per the v5.0q README, drop spanning-deletion ('*') alleles before truvari.
        bcftools view -e 'ALT="*"' -Ou "~{vcf}" | bcftools sort -Oz -o "~{label}.vcf.gz"
        bcftools index --tbi "~{label}.vcf.gz"
    >>>

    output {
        File out_vcf = "~{label}.vcf.gz"
        File out_tbi = "~{label}.vcf.gz.tbi"
    }

    runtime {
        docker: docker
        cpu: 1
        memory: "2 GiB"
    }
}

task Pbsv {
    input {
        File bam
        File bai
        File ref_fasta
        File ref_fai
        String region
        File trf_bed
        String docker
        Int cpu = 4
        Int memory_gb = 8
    }

    command <<<
        set -euo pipefail
        res_t0=$(awk '{print $1}' /proc/uptime)

        ln -s "~{bam}" in.bam; ln -s "~{bai}" in.bam.bai
        ln -s "~{ref_fasta}" ref.fa; ln -s "~{ref_fai}" ref.fa.fai
        pbsv discover --hifi --region "~{region}" --tandem-repeats "~{trf_bed}" in.bam in.svsig.gz
        pbsv call --hifi -j ~{cpu} ref.fa in.svsig.gz pbsv.vcf

        res_t1=$(awk '{print $1}' /proc/uptime)
        printf '{"task":"Pbsv","label":"pbsv","wall_seconds":%s,"cpu_seconds":%s,"peak_memory_bytes":%s,"requested_cpu":%s,"requested_memory_gb":%s,"image":"%s"}\n' \
            "$(awk -v a="$res_t0" -v b="$res_t1" 'BEGIN{print b-a}')" \
            "$(awk '/^usage_usec/{print $2/1e6}' /sys/fs/cgroup/cpu.stat 2>/dev/null || echo -1)" \
            "$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo -1)" ~{cpu} ~{memory_gb} "~{docker}" > resources.json
    >>>

    output {
        File vcf = "pbsv.vcf"
        File resources = "resources.json"
    }

    runtime {
        docker: docker
        cpu: cpu
        memory: "~{memory_gb} GiB"
        disks: "local-disk 20 HDD"
    }
}

task Sniffles {
    input {
        File bam
        File bai
        File ref_fasta
        File ref_fai
        File trf_bed
        String docker
        Int cpu = 4
        Int memory_gb = 8
    }

    command <<<
        set -euo pipefail
        res_t0=$(awk '{print $1}' /proc/uptime)

        ln -s "~{bam}" in.bam; ln -s "~{bai}" in.bam.bai
        ln -s "~{ref_fasta}" ref.fa; ln -s "~{ref_fai}" ref.fa.fai
        sniffles --input in.bam --vcf sniffles.vcf --reference ref.fa --tandem-repeats "~{trf_bed}" \
            --threads ~{cpu} --allow-overwrite

        res_t1=$(awk '{print $1}' /proc/uptime)
        printf '{"task":"Sniffles","label":"sniffles","wall_seconds":%s,"cpu_seconds":%s,"peak_memory_bytes":%s,"requested_cpu":%s,"requested_memory_gb":%s,"image":"%s"}\n' \
            "$(awk -v a="$res_t0" -v b="$res_t1" 'BEGIN{print b-a}')" \
            "$(awk '/^usage_usec/{print $2/1e6}' /sys/fs/cgroup/cpu.stat 2>/dev/null || echo -1)" \
            "$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo -1)" ~{cpu} ~{memory_gb} "~{docker}" > resources.json
    >>>

    output {
        File vcf = "sniffles.vcf"
        File resources = "resources.json"
    }

    runtime {
        docker: docker
        cpu: cpu
        memory: "~{memory_gb} GiB"
        disks: "local-disk 20 HDD"
    }
}

task SortIndexVcf {
    input {
        File vcf
        String label
        String region
        String docker
    }

    command <<<
        set -euo pipefail
        # Sort (TRGT output is unsorted), compress, index, then keep records starting inside the region:
        # reads were fetched with padding, so callers can report events just outside it.
        bcftools sort -Oz -o tmp.vcf.gz "~{vcf}"
        bcftools index --tbi tmp.vcf.gz
        bcftools view --regions "~{region}" --regions-overlap pos -Oz -o "~{label}.vcf.gz" tmp.vcf.gz
        bcftools index --tbi "~{label}.vcf.gz"
    >>>

    output {
        File out_vcf = "~{label}.vcf.gz"
        File out_tbi = "~{label}.vcf.gz.tbi"
    }

    runtime {
        docker: docker
        cpu: 1
        memory: "2 GiB"
    }
}

task Truvari {
    input {
        File truth_vcf
        File truth_tbi
        File query_vcf
        File query_tbi
        File bed
        File ref_fasta
        File ref_fai
        String label
        String docker
        Int refine_timeout_minutes = 30
        Int cpu = 2
        Int memory_gb = 4
    }

    command <<<
        set -euo pipefail
        res_t0=$(awk '{print $1}' /proc/uptime)

        ln -s "~{truth_vcf}" truth.vcf.gz; ln -s "~{truth_tbi}" truth.vcf.gz.tbi
        ln -s "~{query_vcf}" query.vcf.gz; ln -s "~{query_tbi}" query.vcf.gz.tbi
        ln -s "~{ref_fasta}" ref.fa; ln -s "~{ref_fai}" ref.fa.fai
        # Matching parameters follow the GIAB v5.0q README: allele-count-aware picking, PASS only,
        # 2 kb reference distance, 5 kb chunking. Then refine re-aligns the regions where the call
        # sets disagree. It runs with MAFFT (bundled in the image) instead of the default POA
        # aligner: on a 40 kb Sniffles region here, POA tried to allocate 32 GiB, failed, and left
        # refine waiting forever at 0% CPU. The timeout turns any such hang into a failure.
        truvari bench -b truth.vcf.gz -c query.vcf.gz -o "truvari_~{label}" -f ref.fa \
            --includebed "~{bed}" --pick ac --passonly -r 2000 -C 5000
        timeout -k 1m ~{refine_timeout_minutes}m truvari refine -f ref.fa --align mafft --threads ~{cpu} "truvari_~{label}"
        cp "truvari_~{label}/summary.json" "~{label}.truvari.json"
        cp "truvari_~{label}/refine.variant_summary.json" "~{label}.truvari.refine.json"

        res_t1=$(awk '{print $1}' /proc/uptime)
        printf '{"task":"Truvari","label":"~{label}","wall_seconds":%s,"cpu_seconds":%s,"peak_memory_bytes":%s,"requested_cpu":%s,"requested_memory_gb":%s,"image":"%s"}\n' \
            "$(awk -v a="$res_t0" -v b="$res_t1" 'BEGIN{print b-a}')" \
            "$(awk '/^usage_usec/{print $2/1e6}' /sys/fs/cgroup/cpu.stat 2>/dev/null || echo -1)" \
            "$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo -1)" ~{cpu} ~{memory_gb} "~{docker}" > resources.json
    >>>

    output {
        File summary = "~{label}.truvari.json"
        File refine_summary = "~{label}.truvari.refine.json"
        File resources = "resources.json"
    }

    runtime {
        docker: docker
        cpu: cpu
        memory: "~{memory_gb} GiB"
    }
}

task Trgt {
    input {
        File bam
        File bai
        File ref_fasta
        File ref_fai
        Array[File] catalogs
        String karyotype
        String docker
        Int cpu = 4
        Int memory_gb = 4
    }

    command <<<
        set -euo pipefail
        res_t0=$(awk '{print $1}' /proc/uptime)

        ln -s "~{bam}" in.bam; ln -s "~{bai}" in.bam.bai
        ln -s "~{ref_fasta}" ref.fa; ln -s "~{ref_fai}" ref.fa.fai
        # One catalogue, de-duplicated by locus ID (the disease catalogue overlaps the general one).
        cat ~{sep=" " catalogs} | sort -k1,1 -k2,2n | awk -F'\t' '{split($4, a, ";"); if (!seen[a[1]]++) print}' > repeats.bed
        trgt genotype --genome ref.fa --reads in.bam --repeats repeats.bed --karyotype "~{karyotype}" \
            --output-prefix trgt --threads ~{cpu}

        res_t1=$(awk '{print $1}' /proc/uptime)
        printf '{"task":"Trgt","label":"trgt","wall_seconds":%s,"cpu_seconds":%s,"peak_memory_bytes":%s,"requested_cpu":%s,"requested_memory_gb":%s,"image":"%s"}\n' \
            "$(awk -v a="$res_t0" -v b="$res_t1" 'BEGIN{print b-a}')" \
            "$(awk '/^usage_usec/{print $2/1e6}' /sys/fs/cgroup/cpu.stat 2>/dev/null || echo -1)" \
            "$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo -1)" ~{cpu} ~{memory_gb} "~{docker}" > resources.json
    >>>

    output {
        File vcf = "trgt.vcf.gz"
        File spanning_bam = "trgt.spanning.bam"
        File repeats = "repeats.bed"
        File resources = "resources.json"
    }

    runtime {
        docker: docker
        cpu: cpu
        memory: "~{memory_gb} GiB"
    }
}

task SortIndexBam {
    input {
        File bam
        String docker
    }

    command <<<
        set -euo pipefail
        samtools sort -o sorted.bam "~{bam}"
        samtools index sorted.bam
    >>>

    output {
        File sorted_bam = "sorted.bam"
        File sorted_bai = "sorted.bam.bai"
    }

    runtime {
        docker: docker
        cpu: 1
        memory: "2 GiB"
    }
}

task TrgtPlot {
    # One SVG per locus: each spanning read as a row, grouped by allele, coloured by motif.
    input {
        File spanning_bam
        File spanning_bai
        File vcf
        File tbi
        File repeats
        File ref_fasta
        File ref_fai
        Array[String] loci
        String docker
    }

    command <<<
        set -euo pipefail
        ln -s "~{spanning_bam}" spanning.bam; ln -s "~{spanning_bai}" spanning.bam.bai
        ln -s "~{vcf}" trgt.vcf.gz; ln -s "~{tbi}" trgt.vcf.gz.tbi
        ln -s "~{ref_fasta}" ref.fa; ln -s "~{ref_fai}" ref.fa.fai
        mkdir plots
        for locus in ~{sep=" " loci}; do
            trgt plot --genome ref.fa --repeats "~{repeats}" --vcf trgt.vcf.gz --spanning-reads spanning.bam \
                --repeat-id "$locus" --image "plots/$locus.svg"
        done
    >>>

    output {
        Array[File] plots = glob("plots/*.svg")
    }

    runtime {
        docker: docker
        cpu: 1
        memory: "2 GiB"
    }
}

task CpgScores {
    input {
        File bam
        File bai
        File ref_fasta
        File ref_fai
        String docker
        Int cpu = 4
        Int memory_gb = 8
    }

    command <<<
        set -euo pipefail
        res_t0=$(awk '{print $1}' /proc/uptime)

        ln -s "~{bam}" in.bam; ln -s "~{bai}" in.bam.bai
        ln -s "~{ref_fasta}" ref.fa; ln -s "~{ref_fai}" ref.fa.fai
        aligned_bam_to_cpg_scores --bam in.bam --ref ref.fa --output-prefix cpg --threads ~{cpu}

        res_t1=$(awk '{print $1}' /proc/uptime)
        printf '{"task":"CpgScores","label":"cpg","wall_seconds":%s,"cpu_seconds":%s,"peak_memory_bytes":%s,"requested_cpu":%s,"requested_memory_gb":%s,"image":"%s"}\n' \
            "$(awk -v a="$res_t0" -v b="$res_t1" 'BEGIN{print b-a}')" \
            "$(awk '/^usage_usec/{print $2/1e6}' /sys/fs/cgroup/cpu.stat 2>/dev/null || echo -1)" \
            "$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo -1)" ~{cpu} ~{memory_gb} "~{docker}" > resources.json
    >>>

    output {
        File combined_bed = "cpg.combined.bed.gz"
        File combined_tbi = "cpg.combined.bed.gz.tbi"
        # Present only when the reads carry HP haplotype tags.
        Array[File] haplotype_beds = glob("cpg.hap*.bed.gz")
        Array[File] haplotype_tbis = glob("cpg.hap*.bed.gz.tbi")
        File resources = "resources.json"
    }

    runtime {
        docker: docker
        cpu: cpu
        memory: "~{memory_gb} GiB"
    }
}

task Handoff {
    input {
        String run_label
        String region
        File script
        Array[File] sv_vcfs
        Array[File] sv_tbis
        Array[File] truvari_summaries
        Array[File] truvari_refined = []
        File trgt_vcf
        File trgt_tbi
        Array[File] trgt_plots = []
        Array[String] highlight = []
        File cpg_bed
        File cpg_tbi
        Array[File] cpg_haplotype_beds = []
        Array[File] cpg_haplotype_tbis = []
        File? cpg_islands
        Int read_count
        Array[File] resources
        String docker
    }

    command <<<
        set -euo pipefail
        python3 "~{script}" --label "~{run_label}" --region "~{region}" --read-count ~{read_count} \
            --sv-vcf ~{sep=" --sv-vcf " sv_vcfs} --index ~{sep=" --index " sv_tbis} \
            --truvari ~{sep=" --truvari " truvari_summaries} \
            ~{true="--truvari-refine " false="" length(truvari_refined) > 0}~{sep=" --truvari-refine " truvari_refined} \
            --trgt-vcf "~{trgt_vcf}" --index "~{trgt_tbi}" \
            ~{true="--plot " false="" length(trgt_plots) > 0}~{sep=" --plot " trgt_plots} \
            ~{true="--highlight " false="" length(highlight) > 0}~{sep=" --highlight " highlight} \
            --cpg-bed "~{cpg_bed}" --index "~{cpg_tbi}" ~{"--cpg-islands " + cpg_islands} \
            ~{true="--cpg-haplotype-bed " false="" length(cpg_haplotype_beds) > 0}~{sep=" --cpg-haplotype-bed " cpg_haplotype_beds} \
            ~{true="--index " false="" length(cpg_haplotype_tbis) > 0}~{sep=" --index " cpg_haplotype_tbis} \
            --resources ~{sep=" --resources " resources} --out handoff
        tar -czf "~{run_label}.handoff.tar.gz" handoff
    >>>

    output {
        File tarball = "~{run_label}.handoff.tar.gz"
        File qc_summary = "handoff/QC_SUMMARY.md"
        File qc_json = "handoff/qc.json"
    }

    runtime {
        docker: docker
        cpu: 1
        memory: "2 GiB"
    }
}
