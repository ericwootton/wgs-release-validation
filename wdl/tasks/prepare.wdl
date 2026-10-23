version 1.0

# Input preparation: a single-contig reference and a read slice whose header matches it.
#
# Every task in this repository writes resources.json (wall time, CPU time, peak memory,
# requested CPU and memory) so runs can be costed afterwards (scripts/estimate_cost.py).
# The prologue/epilogue lines are repeated in each task because WDL 1.0 has no macros.

task FetchReference {
    input {
        String? ref_url        # remote FASTA with .fai alongside (htslib reads https)
        File? ref_fasta        # or a local FASTA / bgzipped FASTA (indexed here)
        String contig
        String docker
        Int cpu = 1
        Int memory_gb = 2
    }

    String source = select_first([ref_fasta, ref_url])

    command <<<
        set -euo pipefail
        res_t0=$(awk '{print $1}' /proc/uptime)

        # Localised inputs are read-only, so link a local FASTA into the working directory,
        # where samtools can write its .fai (and .gzi, if bgzipped).
        src="~{source}"
        if [ -e "$src" ]; then
            case "$src" in *.gz) ln -s "$src" input.fa.gz; src=input.fa.gz ;; *) ln -s "$src" input.fa; src=input.fa ;; esac
        fi
        samtools faidx "$src" "~{contig}" > ref.fa
        samtools faidx ref.fa
        samtools dict ref.fa -o ref.dict
        test "$(cut -f1 ref.fa.fai)" = "~{contig}"

        res_t1=$(awk '{print $1}' /proc/uptime)
        printf '{"task":"FetchReference","wall_seconds":%s,"cpu_seconds":%s,"peak_memory_bytes":%s,"requested_cpu":%s,"requested_memory_gb":%s,"image":"%s"}\n' \
            "$(awk -v a="$res_t0" -v b="$res_t1" 'BEGIN{print b-a}')" \
            "$(awk '/^usage_usec/{print $2/1e6}' /sys/fs/cgroup/cpu.stat 2>/dev/null || echo -1)" \
            "$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo -1)" ~{cpu} ~{memory_gb} "~{docker}" > resources.json
    >>>

    output {
        File fasta = "ref.fa"
        File fai = "ref.fa.fai"
        File dict = "ref.dict"
        File resources = "resources.json"
    }

    runtime {
        docker: docker
        cpu: cpu
        memory: "~{memory_gb} GiB"
        disks: "local-disk 10 HDD"
    }
}

task FetchReadsSlice {
    input {
        String? reads_url      # remote BAM with .bai alongside
        File? reads_bam        # or a local BAM + index
        File? reads_bai
        String region          # samtools-style, 1-based inclusive
        String contig
        Int pad = 1000
        String docker
        Int cpu = 2
        Int memory_gb = 4
    }

    String source = select_first([reads_bam, reads_url])

    command <<<
        set -euo pipefail
        res_t0=$(awk '{print $1}' /proc/uptime)

        span="~{region}"; span="${span#*:}"
        start=$(( ${span%-*} - ~{pad} )); [ "$start" -ge 1 ] || start=1
        end=$(( ${span#*-} + ~{pad} ))
        padded="~{contig}:${start}-${end}"

        index=()
        if [ -n "~{reads_bai}" ]; then index=(-X "~{source}" "~{reads_bai}"); fi
        if [ ${#index[@]} -gt 0 ]; then
            samtools view -b -o raw.bam "${index[@]}" "$padded"
        else
            samtools view -b -o raw.bam "~{source}" "$padded"
        fi

        # Keep only the analysed contig in the header, so it matches the single-contig reference.
        # GATK 4.7 and DeepVariant 1.10 accept extra header contigs (tested in CS-02), but the slice
        # is handed to other tools and to ngs-preflight, which warns on them (REF002).
        # `samtools reheader` cannot do this: BAM records store contigs as numeric indexes into
        # the @SQ list, so deleting earlier @SQ lines would silently move reads to the wrong
        # contig. Re-encoding through SAM text maps reads by name instead. Mates on other
        # contigs become "mate unmapped" for the purposes of this slice.
        samtools view -h raw.bam \
            | awk -v c="~{contig}" 'BEGIN{OFS="\t"} /^@SQ/ {if ($2 == "SN:" c) print; next} /^@/ {print; next} {if ($7 != "=" && $7 != c) {$7 = "*"; $8 = 0}; print}' \
            | samtools view -b -o slice.bam -
        samtools index slice.bam
        samtools view -c slice.bam > read_count.txt
        rm raw.bam

        res_t1=$(awk '{print $1}' /proc/uptime)
        printf '{"task":"FetchReadsSlice","wall_seconds":%s,"cpu_seconds":%s,"peak_memory_bytes":%s,"requested_cpu":%s,"requested_memory_gb":%s,"image":"%s"}\n' \
            "$(awk -v a="$res_t0" -v b="$res_t1" 'BEGIN{print b-a}')" \
            "$(awk '/^usage_usec/{print $2/1e6}' /sys/fs/cgroup/cpu.stat 2>/dev/null || echo -1)" \
            "$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo -1)" ~{cpu} ~{memory_gb} "~{docker}" > resources.json
    >>>

    output {
        File bam = "slice.bam"
        File bai = "slice.bam.bai"
        Int read_count = read_int("read_count.txt")
        File resources = "resources.json"
    }

    runtime {
        docker: docker
        cpu: cpu
        memory: "~{memory_gb} GiB"
        disks: "local-disk 20 HDD"
    }
}

task Preflight {
    # Checks the inputs with ngs-preflight (github.com/ericwootton/ngs-preflight) before any compute
    # is spent: BED contig names, coordinates and sort order against the reference, and the BAM
    # header against the reference. Errors fail the workflow; warnings are reported and allowed.
    input {
        File ref_fai
        File region_bed
        File confident_bed
        File bam
        String sample_id = "HG002"
        String docker
        Int cpu = 1
        Int memory_gb = 1
    }

    command <<<
        set -uo pipefail
        res_t0=$(awk '{print $1}' /proc/uptime)

        mkdir -p reads; ln -s "~{bam}" reads/slice.bam
        printf 'sample_id,fastq_1,sex\n%s,slice.bam,male\n' "~{sample_id}" > samples.csv
        args=(--samplesheet samples.csv --reads-dir reads --bed "~{region_bed}" --bed "~{confident_bed}"
              --reference "~{ref_fai}" --expected-build GRCh38)
        preflight check "${args[@]}" --format markdown --out preflight.md
        preflight check "${args[@]}" --format json --out preflight.json
        status=$?
        cat preflight.md >&2

        res_t1=$(awk '{print $1}' /proc/uptime)
        printf '{"task":"Preflight","wall_seconds":%s,"cpu_seconds":%s,"peak_memory_bytes":%s,"requested_cpu":%s,"requested_memory_gb":%s,"image":"%s"}\n' \
            "$(awk -v a="$res_t0" -v b="$res_t1" 'BEGIN{print b-a}')" \
            "$(awk '/^usage_usec/{print $2/1e6}' /sys/fs/cgroup/cpu.stat 2>/dev/null || echo -1)" \
            "$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo -1)" ~{cpu} ~{memory_gb} "~{docker}" > resources.json
        # 0 pass, 2 warnings only: continue. 1 errors, 3 tool/usage error: stop here.
        if [ "$status" -eq 1 ] || [ "$status" -eq 3 ]; then
            echo "ngs-preflight found blocking problems (exit $status); see preflight.md" >&2
            exit 1
        fi
    >>>

    output {
        File report_json = "preflight.json"
        File report_md = "preflight.md"
        File resources = "resources.json"
    }

    runtime {
        docker: docker
        cpu: cpu
        memory: "~{memory_gb} GiB"
    }
}
