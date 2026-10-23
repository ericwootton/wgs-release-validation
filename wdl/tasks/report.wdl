version 1.0

# Turn hap.py output into the metrics table used by the README and the regression gate.

task SummarizeMetrics {
    input {
        Array[File] extended_csvs
        Array[String] labels           # same order as extended_csvs
        File summarize_script          # scripts/summarize_happy.py (standard library only)
        File mosdepth_summary
        String run_label
        String region
        String truth_set
        Array[String] tool_versions    # "tool=image" strings, recorded in metrics.json
        String docker
        Int cpu = 1
        Int memory_gb = 1
    }

    command <<<
        set -euo pipefail
        res_t0=$(awk '{print $1}' /proc/uptime)

        labels=(~{sep=" " labels})
        csvs=(~{sep=" " extended_csvs})
        args=()
        for i in "${!labels[@]}"; do args+=(--extended "${labels[$i]}=${csvs[$i]}"); done
        versions=()
        # One entry per line: parameter values such as "gatk_args=--minimum-mapping-quality 40" contain spaces.
        while IFS= read -r v; do versions+=(--tool-version "$v"); done < "~{write_lines(tool_versions)}"
        python3 "~{summarize_script}" "${args[@]}" "${versions[@]}" \
            --run-label "~{run_label}" --region "~{region}" --truth-set "~{truth_set}" \
            --mosdepth "~{mosdepth_summary}" \
            --out-json metrics.json --out-md metrics.md

        res_t1=$(awk '{print $1}' /proc/uptime)
        printf '{"task":"SummarizeMetrics","wall_seconds":%s,"cpu_seconds":%s,"peak_memory_bytes":%s,"requested_cpu":%s,"requested_memory_gb":%s,"image":"%s"}\n' \
            "$(awk -v a="$res_t0" -v b="$res_t1" 'BEGIN{print b-a}')" \
            "$(awk '/^usage_usec/{print $2/1e6}' /sys/fs/cgroup/cpu.stat 2>/dev/null || echo -1)" \
            "$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo -1)" ~{cpu} ~{memory_gb} "~{docker}" > resources.json
    >>>

    output {
        File metrics_json = "metrics.json"
        File metrics_md = "metrics.md"
        File resources = "resources.json"
    }

    runtime {
        docker: docker
        cpu: cpu
        memory: "~{memory_gb} GiB"
        disks: "local-disk 5 HDD"
    }
}
