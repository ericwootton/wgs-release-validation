version 1.0

# Input and output QC: coverage over the analysed region and per-callset variant statistics.

task Mosdepth {
    input {
        File bam
        File bai
        File region_bed
        String docker
        Int cpu = 2
        Int memory_gb = 2
    }

    command <<<
        set -euo pipefail
        res_t0=$(awk '{print $1}' /proc/uptime)

        ln -s "~{bam}" reads.bam; ln -s "~{bai}" reads.bam.bai
        mosdepth --threads ~{cpu} --no-per-base --fast-mode \
            --by "~{region_bed}" --thresholds 10,20,30 \
            coverage reads.bam

        res_t1=$(awk '{print $1}' /proc/uptime)
        printf '{"task":"Mosdepth","wall_seconds":%s,"cpu_seconds":%s,"peak_memory_bytes":%s,"requested_cpu":%s,"requested_memory_gb":%s,"image":"%s"}\n' \
            "$(awk -v a="$res_t0" -v b="$res_t1" 'BEGIN{print b-a}')" \
            "$(awk '/^usage_usec/{print $2/1e6}' /sys/fs/cgroup/cpu.stat 2>/dev/null || echo -1)" \
            "$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo -1)" ~{cpu} ~{memory_gb} "~{docker}" > resources.json
    >>>

    output {
        File summary = "coverage.mosdepth.summary.txt"
        File thresholds = "coverage.thresholds.bed.gz"
        File regions = "coverage.regions.bed.gz"
        File resources = "resources.json"
    }

    runtime {
        docker: docker
        cpu: cpu
        memory: "~{memory_gb} GiB"
        disks: "local-disk 10 HDD"
    }
}

task VariantQC {
    input {
        File vcf
        File tbi
        File ref_fasta
        File ref_fai
        String label
        String docker
        Int cpu = 1
        Int memory_gb = 2
    }

    command <<<
        set -euo pipefail
        res_t0=$(awk '{print $1}' /proc/uptime)

        ln -s "~{ref_fasta}" ref.fa; ln -s "~{ref_fai}" ref.fa.fai
        bcftools stats --fasta-ref ref.fa "~{vcf}" > "~{label}.bcftools_stats.txt"

        res_t1=$(awk '{print $1}' /proc/uptime)
        printf '{"task":"VariantQC","label":"~{label}","wall_seconds":%s,"cpu_seconds":%s,"peak_memory_bytes":%s,"requested_cpu":%s,"requested_memory_gb":%s,"image":"%s"}\n' \
            "$(awk -v a="$res_t0" -v b="$res_t1" 'BEGIN{print b-a}')" \
            "$(awk '/^usage_usec/{print $2/1e6}' /sys/fs/cgroup/cpu.stat 2>/dev/null || echo -1)" \
            "$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo -1)" ~{cpu} ~{memory_gb} "~{docker}" > resources.json
    >>>

    output {
        File stats = "~{label}.bcftools_stats.txt"
        File resources = "resources.json"
    }

    runtime {
        docker: docker
        cpu: cpu
        memory: "~{memory_gb} GiB"
        disks: "local-disk 10 HDD"
    }
}
