version 1.0

# Normalisation and GIAB benchmarking with hap.py (vcfeval engine) and GIAB stratifications.

task NormalizeVcf {
    input {
        File vcf               # VCF or bgzipped VCF
        File ref_fasta
        File ref_fai
        String label
        String extra_norm_args = ""   # e.g. for testing the regression gate
        String docker
        Int cpu = 1
        Int memory_gb = 2
    }

    command <<<
        set -euo pipefail
        res_t0=$(awk '{print $1}' /proc/uptime)

        ln -s "~{ref_fasta}" ref.fa; ln -s "~{ref_fai}" ref.fa.fai
        # Split multi-allelic records, left-align against the reference, keep PASS (or unfiltered)
        # records only, then sort and index.
        bcftools norm --multiallelics -any --fasta-ref ref.fa ~{extra_norm_args} -Ou "~{vcf}" \
            | bcftools view --apply-filters PASS,. -Ou \
            | bcftools sort -Oz -o "~{label}.norm.vcf.gz"
        bcftools index --tbi "~{label}.norm.vcf.gz"
        bcftools view -H "~{label}.norm.vcf.gz" | wc -l | tr -d ' ' > n_records.txt

        res_t1=$(awk '{print $1}' /proc/uptime)
        printf '{"task":"NormalizeVcf","label":"~{label}","wall_seconds":%s,"cpu_seconds":%s,"peak_memory_bytes":%s,"requested_cpu":%s,"requested_memory_gb":%s,"image":"%s"}\n' \
            "$(awk -v a="$res_t0" -v b="$res_t1" 'BEGIN{print b-a}')" \
            "$(awk '/^usage_usec/{print $2/1e6}' /sys/fs/cgroup/cpu.stat 2>/dev/null || echo -1)" \
            "$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo -1)" ~{cpu} ~{memory_gb} "~{docker}" > resources.json
    >>>

    output {
        File norm_vcf = "~{label}.norm.vcf.gz"
        File norm_tbi = "~{label}.norm.vcf.gz.tbi"
        Int n_records = read_int("n_records.txt")
        File resources = "resources.json"
    }

    runtime {
        docker: docker
        cpu: cpu
        memory: "~{memory_gb} GiB"
        disks: "local-disk 10 HDD"
    }
}

task HappyBenchmark {
    input {
        File truth_vcf
        File truth_tbi
        File query_vcf
        File query_tbi
        File confident_bed
        File ref_fasta
        File ref_fai
        Array[File] strat_beds
        Array[String] strat_names   # one per strat_beds entry, in the same order
        String label
        String docker
        Int cpu = 4
        Int memory_gb = 8
    }

    command <<<
        set -euo pipefail
        res_t0=$(awk '{print $1}' /proc/uptime)

        ln -s "~{ref_fasta}" ref.fa; ln -s "~{ref_fai}" ref.fa.fai
        # hap.py resolves stratification paths relative to the TSV, so write absolute paths.
        test ~{length(strat_names)} -eq ~{length(strat_beds)}
        paste ~{write_lines(strat_names)} ~{write_lines(strat_beds)} > strat.tsv

        mkdir -p happy
        hap.py "~{truth_vcf}" "~{query_vcf}" \
            --false-positives "~{confident_bed}" \
            --reference ref.fa \
            --engine vcfeval \
            --stratification strat.tsv \
            --pass-only \
            --threads ~{cpu} \
            --report-prefix "happy/~{label}"

        res_t1=$(awk '{print $1}' /proc/uptime)
        printf '{"task":"HappyBenchmark","label":"~{label}","wall_seconds":%s,"cpu_seconds":%s,"peak_memory_bytes":%s,"requested_cpu":%s,"requested_memory_gb":%s,"image":"%s"}\n' \
            "$(awk -v a="$res_t0" -v b="$res_t1" 'BEGIN{print b-a}')" \
            "$(awk '/^usage_usec/{print $2/1e6}' /sys/fs/cgroup/cpu.stat 2>/dev/null || echo -1)" \
            "$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo -1)" ~{cpu} ~{memory_gb} "~{docker}" > resources.json
    >>>

    output {
        File summary_csv = "happy/~{label}.summary.csv"
        File extended_csv = "happy/~{label}.extended.csv"
        File annotated_vcf = "happy/~{label}.vcf.gz"
        File annotated_tbi = "happy/~{label}.vcf.gz.tbi"
        File metrics_json = "happy/~{label}.metrics.json.gz"
        File resources = "resources.json"
    }

    runtime {
        docker: docker
        cpu: cpu
        memory: "~{memory_gb} GiB"
        disks: "local-disk 20 HDD"
    }
}
