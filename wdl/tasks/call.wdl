version 1.0

# Germline small-variant callers. Thread counts are fixed so repeated runs are comparable.

task HaplotypeCaller {
    input {
        File ref_fasta
        File ref_fai
        File ref_dict
        File bam
        File bai
        String region
        String docker
        String extra_args = ""   # only for exercising the regression gate (INC-01)
        File? after_preflight      # not read: makes calling wait until Preflight has passed
        Int threads = 4
        Int cpu = 4
        Int memory_gb = 6
    }

    Int java_gb = memory_gb - 1

    command <<<
        set -euo pipefail
        res_t0=$(awk '{print $1}' /proc/uptime)

        ln -s "~{ref_fasta}" ref.fa; ln -s "~{ref_fai}" ref.fa.fai; ln -s "~{ref_dict}" ref.dict
        ln -s "~{bam}" reads.bam; ln -s "~{bai}" reads.bam.bai
        gatk --java-options "-Xmx~{java_gb}g -XX:ParallelGCThreads=1" HaplotypeCaller \
            -R ref.fa -I reads.bam -L "~{region}" \
            --native-pair-hmm-threads ~{threads} ~{extra_args} \
            -O calls.vcf.gz

        res_t1=$(awk '{print $1}' /proc/uptime)
        printf '{"task":"HaplotypeCaller","wall_seconds":%s,"cpu_seconds":%s,"peak_memory_bytes":%s,"requested_cpu":%s,"requested_memory_gb":%s,"image":"%s"}\n' \
            "$(awk -v a="$res_t0" -v b="$res_t1" 'BEGIN{print b-a}')" \
            "$(awk '/^usage_usec/{print $2/1e6}' /sys/fs/cgroup/cpu.stat 2>/dev/null || echo -1)" \
            "$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo -1)" ~{cpu} ~{memory_gb} "~{docker}" > resources.json
    >>>

    output {
        File vcf = "calls.vcf.gz"
        File tbi = "calls.vcf.gz.tbi"
        File resources = "resources.json"
    }

    runtime {
        docker: docker
        cpu: cpu
        memory: "~{memory_gb} GiB"
        disks: "local-disk 20 HDD"
    }
}

task DeepVariant {
    input {
        File ref_fasta
        File ref_fai
        File bam
        File bai
        String region
        String docker
        String model_type = "WGS"
        File? after_preflight      # not read: makes calling wait until Preflight has passed
        Int shards = 4
        Int cpu = 4
        Int memory_gb = 8
    }

    command <<<
        set -euo pipefail
        res_t0=$(awk '{print $1}' /proc/uptime)

        ln -s "~{ref_fasta}" ref.fa; ln -s "~{ref_fai}" ref.fa.fai
        ln -s "~{bam}" reads.bam; ln -s "~{bai}" reads.bam.bai

        # When the kernel kills one of DeepVariant's worker processes for exceeding the memory
        # limit, the others can wait about five minutes and then exit 247 with no error (CS-03).
        # Watch the container's OOM-kill counter and stop at once with a message that says why.
        oom_kills() { awk '/^oom_kill /{print $2}' /sys/fs/cgroup/memory.events 2>/dev/null || echo 0; }
        oom_error() {
            echo "error: a DeepVariant process was killed for running out of memory (memory_gb=~{memory_gb}," \
                "shards=~{shards}). Raise deepvariant_memory_gb or lower deepvariant_shards;" \
                "see docs/case-studies/CS-03-deepvariant-memory.md" >&2
        }
        oom_before=$(oom_kills)
        # setsid gives DeepVariant and its workers their own process group, so the guard can stop
        # exactly those processes (on backends without a PID namespace, `kill 0` could reach others).
        setsid /opt/deepvariant/bin/run_deepvariant \
            --model_type=~{model_type} \
            --ref=ref.fa --reads=reads.bam --regions="~{region}" \
            --output_vcf=calls.vcf.gz \
            --num_shards=~{shards} \
            --intermediate_results_dir=tmp &
        dv=$!
        oom=0
        while kill -0 "$dv" 2>/dev/null; do
            if [ "$(oom_kills)" != "$oom_before" ]; then
                oom=1
                oom_error
                kill -TERM -- "-$dv" 2>/dev/null || true
                for _ in 1 2 3 4 5; do kill -0 "$dv" 2>/dev/null || break; sleep 2; done
                kill -KILL -- "-$dv" 2>/dev/null || true
                break
            fi
            sleep 2
        done
        dv_rc=0
        wait "$dv" || dv_rc=$?
        # Check again: the kill may have come less than one poll before DeepVariant exited.
        if [ "$oom" = 0 ] && [ "$dv_rc" -ne 0 ] && [ "$(oom_kills)" != "$oom_before" ]; then
            oom=1
            oom_error
        fi
        if [ "$oom" = 1 ]; then exit $(( dv_rc == 0 ? 1 : dv_rc )); fi
        if [ "$dv_rc" -ne 0 ]; then exit "$dv_rc"; fi
        rm -rf tmp

        res_t1=$(awk '{print $1}' /proc/uptime)
        printf '{"task":"DeepVariant","wall_seconds":%s,"cpu_seconds":%s,"peak_memory_bytes":%s,"requested_cpu":%s,"requested_memory_gb":%s,"image":"%s"}\n' \
            "$(awk -v a="$res_t0" -v b="$res_t1" 'BEGIN{print b-a}')" \
            "$(awk '/^usage_usec/{print $2/1e6}' /sys/fs/cgroup/cpu.stat 2>/dev/null || echo -1)" \
            "$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo -1)" ~{cpu} ~{memory_gb} "~{docker}" > resources.json
    >>>

    output {
        File vcf = "calls.vcf.gz"
        File tbi = "calls.vcf.gz.tbi"
        File resources = "resources.json"
    }

    runtime {
        docker: docker
        cpu: cpu
        memory: "~{memory_gb} GiB"
        disks: "local-disk 30 HDD"
    }
}
