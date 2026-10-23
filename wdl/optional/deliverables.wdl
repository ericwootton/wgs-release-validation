version 1.0

# Custom deliverables built from validated outputs (spec §2.15):
#   ReadSupportSlices   one small indexed BAM per requested variant, plus ref/alt read counts
#   CollectionVcf       several single-sample VCFs merged into one, with cohort AC/AN/AF
#   TargetedTsvExtract  chosen VCF fields over a BED, as a TSV with a data dictionary
# Each task writes a README.md describing what the recipient is getting.

import "../tasks/prepare.wdl" as prepare

workflow Deliverables {
    input {
        String run_label
        String contig = "chr20"
        String? ref_url          # remote FASTA with .fai alongside, or
        File? ref_fasta          # a local one; either way only `contig` is extracted

        # ReadSupportSlices
        File? bam
        File? bai
        File? sites_tsv          # chrom, pos, ref, alt; header line allowed if it starts with '#'
        Int pad = 200

        # CollectionVcf
        Array[File] sample_vcfs = []   # plain or bgzipped, one sample each
        File? region_bed

        # TargetedTsvExtract
        File? extract_vcf
        File? extract_tbi
        File? extract_bed
        Array[String] fields = ["CHROM", "POS", "REF", "ALT", "QUAL", "FILTER", "FORMAT/GT", "FORMAT/DP"]

        String samtools_docker = "quay.io/biocontainers/samtools:1.24--h9dcdb79_1@sha256:a130447589651ed09252aa95a5e4f4132942cdb54d835d81a04a9a930d656561"
        String bcftools_docker = "quay.io/biocontainers/bcftools:1.24--h118bc1c_4@sha256:186c45de3059dbb1837006c27788284c89d17f8e693e7804624b6cf6ca5caca0"
    }

    call prepare.FetchReference {
        input: ref_url = ref_url, ref_fasta = ref_fasta, contig = contig, docker = samtools_docker
    }

    if (defined(bam) && defined(sites_tsv)) {
        call ReadSupportSlices {
            input:
                bam = select_first([bam]),
                bai = select_first([bai]),
                sites_tsv = select_first([sites_tsv]),
                pad = pad,
                label = run_label,
                docker = samtools_docker
        }
        call AlleleSupport {
            input:
                bam = select_first([bam]),
                bai = select_first([bai]),
                sites_tsv = select_first([sites_tsv]),
                ref_fasta = FetchReference.fasta,
                ref_fai = FetchReference.fai,
                label = run_label,
                docker = bcftools_docker
        }
    }

    if (length(sample_vcfs) > 1) {
        call CollectionVcf {
            input:
                vcfs = sample_vcfs,
                region_bed = region_bed,
                ref_fasta = FetchReference.fasta,
                ref_fai = FetchReference.fai,
                label = run_label,
                docker = bcftools_docker
        }
    }

    if (defined(extract_vcf)) {
        call TargetedTsvExtract {
            input:
                vcf = select_first([extract_vcf]),
                tbi = select_first([extract_tbi]),
                bed = extract_bed,
                fields = fields,
                ref_fasta = FetchReference.fasta,
                ref_fai = FetchReference.fai,
                label = run_label,
                docker = bcftools_docker
        }
    }

    output {
        Array[File]? site_bams = ReadSupportSlices.site_bams
        Array[File]? site_bais = ReadSupportSlices.site_bais
        File? merged_sites_bam = ReadSupportSlices.merged_bam
        File? allele_support_tsv = AlleleSupport.support_tsv
        File? collection_vcf = CollectionVcf.vcf
        File? collection_tbi = CollectionVcf.tbi
        File? extract_tsv = TargetedTsvExtract.tsv
        File? extract_dictionary = TargetedTsvExtract.dictionary
        File? sites_readme = ReadSupportSlices.readme
        File? sites_index_tsv = ReadSupportSlices.index_tsv
        File? collection_readme = CollectionVcf.readme
    }

    parameter_meta {
        sites_tsv: "Variants to slice around: chrom, pos (1-based), ref, alt. Tab-separated."
        pad: "Bases either side of each site to keep in its BAM slice."
        sample_vcfs: "Single-sample VCFs (plain or bgzipped) to merge."
        region_bed: "Optional BED restricting the collection VCF."
        fields: "bcftools query fields: CHROM/POS/REF/ALT/QUAL/FILTER, INFO/<tag>, FORMAT/<tag>."
    }
}

task ReadSupportSlices {
    input {
        File bam
        File bai
        File sites_tsv
        Int pad
        String label
        String docker
        Int cpu = 1
        Int memory_gb = 2
    }

    command <<<
        set -euo pipefail
        res_t0=$(awk '{print $1}' /proc/uptime)

        ln -s "~{bam}" in.bam; ln -s "~{bai}" in.bam.bai
        mkdir -p slices
        grep -v '^#' "~{sites_tsv}" | while IFS=$'\t' read -r chrom pos ref alt _; do
            start=$(( pos > ~{pad} ? pos - ~{pad} : 1 )); end=$(( pos + ${#ref} - 1 + ~{pad} ))
            name="${chrom}_${pos}_${ref:0:10}_${alt:0:10}"
            samtools view -b -o "slices/${name}.bam" in.bam "${chrom}:${start}-${end}"
            samtools index "slices/${name}.bam"
            printf '%s\t%s\t%s\t%s\t%s:%s-%s\tslices/%s.bam\t%s\n' "$chrom" "$pos" "$ref" "$alt" \
                "$chrom" "$start" "$end" "$name" "$(samtools view -c "slices/${name}.bam")"
        done > slices.tsv
        # One merged BAM for viewers that prefer a single file.
        samtools merge -f -o "~{label}.sites.bam" slices/*.bam
        samtools index "~{label}.sites.bam"

        {
            echo "# Read-supporting BAM slices (~{label})"
            echo
            echo "One small BAM per requested variant, holding every read that overlaps the site"
            echo "plus ~{pad} bases either side, and \`~{label}.sites.bam\` with all of them merged."
            echo "Open any of them in IGV with the GRCh38 reference. Reads are copied unchanged from the"
            echo "analysed BAM; nothing is realigned or filtered. Counts of reads supporting each allele"
            echo "are in the allele-support table delivered alongside."
            echo
            echo "In that table, \`alleles_seen\` and \`allele_depths\` list the alleles in the reads and"
            echo "the reads behind each (\`<*>\` is any other allele), counting reads at the mapping-quality"
            echo "threshold in the \`depth_mapq\` column name or above. \`depth_any_mapq\` counts reads at"
            echo "any mapping quality. Both leave out duplicate, secondary and QC-failed reads, reads in"
            echo "anomalous pairs, and bases below base quality 13. A site can have two rows when the"
            echo "reads also show an indel there."
            echo
            echo "| Site | Ref | Alt | Region | File | Reads |"
            echo "|---|---|---|---|---|---:|"
            awk -F'\t' '{printf "| %s:%s | %s | %s | %s | %s | %s |\n", $1, $2, $3, $4, $5, $6, $7}' slices.tsv
        } > README.md

        res_t1=$(awk '{print $1}' /proc/uptime)
        printf '{"task":"ReadSupportSlices","label":"~{label}","wall_seconds":%s,"cpu_seconds":%s,"peak_memory_bytes":%s,"requested_cpu":%s,"requested_memory_gb":%s,"image":"%s"}\n' \
            "$(awk -v a="$res_t0" -v b="$res_t1" 'BEGIN{print b-a}')" \
            "$(awk '/^usage_usec/{print $2/1e6}' /sys/fs/cgroup/cpu.stat 2>/dev/null || echo -1)" \
            "$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo -1)" ~{cpu} ~{memory_gb} "~{docker}" > resources.json
    >>>

    output {
        Array[File] site_bams = glob("slices/*.bam")
        Array[File] site_bais = glob("slices/*.bam.bai")
        File merged_bam = "~{label}.sites.bam"
        File merged_bai = "~{label}.sites.bam.bai"
        File index_tsv = "slices.tsv"
        File readme = "README.md"
        File resources = "resources.json"
    }

    runtime {
        docker: docker
        cpu: cpu
        memory: "~{memory_gb} GiB"
        disks: "local-disk 10 HDD"
    }
}

task AlleleSupport {
    input {
        File bam
        File bai
        File sites_tsv
        File ref_fasta
        File ref_fai
        String label
        String docker
        Int min_mapq = 20
        Int min_baseq = 13
        Int cpu = 1
        Int memory_gb = 2
    }

    command <<<
        set -euo pipefail
        res_t0=$(awk '{print $1}' /proc/uptime)

        ln -s "~{bam}" in.bam; ln -s "~{bai}" in.bam.bai
        ln -s "~{ref_fasta}" ref.fa; ln -s "~{ref_fai}" ref.fa.fai
        grep -v '^#' "~{sites_tsv}" | awk -F'\t' 'BEGIN{OFS="\t"} {print $1, $2}' | sort -k1,1 -k2,2n > targets.tsv
        # Per-allele depth (AD) from a pileup at exactly the requested positions. Alleles are the ones
        # seen in the reads, so they may differ from the requested ALT; <*> is "any other allele".
        # A second pileup without the MAPQ filter gives the depth before filtering, so a site whose
        # reads all map ambiguously (MAPQ 0) shows up as 0 of N instead of disappearing.
        pileup() {
            bcftools mpileup --fasta-ref ref.fa --targets-file targets.tsv --min-MQ "$1" --min-BQ ~{min_baseq} \
                --annotate FORMAT/AD,FORMAT/DP --max-depth 10000 -Ou in.bam
        }
        pileup ~{min_mapq} | bcftools query -f '%CHROM\t%POS\t%REF\t%ALT\t[%AD]\t[%DP]\n' > filtered.tsv
        pileup 0 | bcftools query -f '%CHROM\t%POS\t[%DP]\n' > unfiltered.tsv
        printf 'chrom\tpos\tref\trequested_alt\talleles_seen\tallele_depths\tdepth_mapq%s\tdepth_any_mapq\n' \
            ~{min_mapq} > "~{label}.allele_support.tsv"
        grep -v '^#' "~{sites_tsv}" | awk -F'\t' 'BEGIN{OFS="\t"}
            FILENAME == "unfiltered.tsv" { k = $1 ":" $2; if ($3 > all[k]) all[k] = $3; next }
            FILENAME == "filtered.tsv"   { k = $1 ":" $2; rows[k] = rows[k] $3 OFS "%ALT%" OFS $4 OFS $5 OFS $6 "\n"; next }
            {
                k = $1 ":" $2; any = (k in all) ? all[k] : 0
                if (k in rows) {
                    n = split(rows[k], lines, "\n")
                    for (i = 1; i < n; i++) { line = lines[i]; sub(/%ALT%/, $4, line); print $1, $2, line, any }
                } else print $1, $2, $3, $4, ".", ".", 0, any
            }' unfiltered.tsv filtered.tsv - >> "~{label}.allele_support.tsv"

        res_t1=$(awk '{print $1}' /proc/uptime)
        printf '{"task":"AlleleSupport","label":"~{label}","wall_seconds":%s,"cpu_seconds":%s,"peak_memory_bytes":%s,"requested_cpu":%s,"requested_memory_gb":%s,"image":"%s"}\n' \
            "$(awk -v a="$res_t0" -v b="$res_t1" 'BEGIN{print b-a}')" \
            "$(awk '/^usage_usec/{print $2/1e6}' /sys/fs/cgroup/cpu.stat 2>/dev/null || echo -1)" \
            "$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo -1)" ~{cpu} ~{memory_gb} "~{docker}" > resources.json
    >>>

    output {
        File support_tsv = "~{label}.allele_support.tsv"
        File resources = "resources.json"
    }

    runtime {
        docker: docker
        cpu: cpu
        memory: "~{memory_gb} GiB"
        disks: "local-disk 10 HDD"
    }
}

task CollectionVcf {
    input {
        Array[File] vcfs
        File? region_bed
        File ref_fasta
        File ref_fai
        String label
        String docker
        Int cpu = 2
        Int memory_gb = 4
    }

    command <<<
        set -euo pipefail
        res_t0=$(awk '{print $1}' /proc/uptime)

        ln -s "~{ref_fasta}" ref.fa; ln -s "~{ref_fai}" ref.fa.fai
        i=0
        merged=()   # in input order: a glob would put s10 before s2
        for vcf in ~{sep=" " vcfs}; do
            i=$((i + 1))
            merged+=("s$i.vcf.gz")
            # Restrict, split multi-allelics and left-align each sample the same way before merging,
            # so the same variant is written the same way in every sample. --targets-file streams
            # the input, so plain or unindexed VCFs work.
            bcftools view ~{if defined(region_bed) then "--targets-file " + region_bed else ""} -Ou "$vcf" \
                | bcftools norm --multiallelics -any --fasta-ref ref.fa -Ou \
                | bcftools annotate --remove INFO -Ou \
                | bcftools sort -Oz -o "s$i.vcf.gz"
            bcftools index --tbi "s$i.vcf.gz"
            bcftools query -l "s$i.vcf.gz" >> samples.txt
        done
        # Duplicate sample names (e.g. every file says "SAMPLE") would make merge refuse; rename them.
        force=""; if [ "$(sort samples.txt | uniq -d | wc -l)" -gt 0 ]; then force="--force-samples"; fi
        bcftools merge $force --merge none -Ou "${merged[@]}" \
            | bcftools +fill-tags -Ou -- -t AC,AN,AF,F_MISSING \
            | bcftools view -Oz -o "~{label}.collection.vcf.gz"
        bcftools index --tbi "~{label}.collection.vcf.gz"

        n_sites=$(bcftools view -H "~{label}.collection.vcf.gz" | wc -l | tr -d ' ')
        {
            echo "# Collection VCF (~{label})"
            echo
            echo "\`~{label}.collection.vcf.gz\` combines $i single-sample VCFs ($(paste -sd, samples.txt)) into one"
            echo "file with one column per sample: $n_sites records. Before merging, ~{if defined(region_bed) then "each input was restricted" else ""}"
            echo "~{if defined(region_bed) then "to the requested region, " else ""}multi-allelic records were split and indels were left-aligned, so"
            echo "a variant has one spelling across samples. The inputs' INFO fields were removed: in a merged"
            echo "record they would describe only one of the samples. Per-sample FORMAT fields are kept."
            echo "INFO/AC, AN and AF are counts across the samples"
            echo "in this file only, not population frequencies. F_MISSING is the fraction of samples with no"
            echo "genotype. A missing genotype (\`./.\`) means the variant was absent from that sample's"
            echo "input VCF. For call sets that list only variant sites, that usually means reference, but"
            echo "not always (the site may be outside that sample's callable or benchmark regions), so it is"
            echo "left missing rather than converted to \`0/0\`."
        } > README.md

        res_t1=$(awk '{print $1}' /proc/uptime)
        printf '{"task":"CollectionVcf","label":"~{label}","wall_seconds":%s,"cpu_seconds":%s,"peak_memory_bytes":%s,"requested_cpu":%s,"requested_memory_gb":%s,"image":"%s"}\n' \
            "$(awk -v a="$res_t0" -v b="$res_t1" 'BEGIN{print b-a}')" \
            "$(awk '/^usage_usec/{print $2/1e6}' /sys/fs/cgroup/cpu.stat 2>/dev/null || echo -1)" \
            "$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo -1)" ~{cpu} ~{memory_gb} "~{docker}" > resources.json
    >>>

    output {
        File vcf = "~{label}.collection.vcf.gz"
        File tbi = "~{label}.collection.vcf.gz.tbi"
        File readme = "README.md"
        File resources = "resources.json"
    }

    runtime {
        docker: docker
        cpu: cpu
        memory: "~{memory_gb} GiB"
        disks: "local-disk 10 HDD"
    }
}

task TargetedTsvExtract {
    input {
        File vcf
        File tbi
        File? bed
        Array[String] fields
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
        ln -s "~{vcf}" in.vcf.gz; ln -s "~{tbi}" in.vcf.gz.tbi
        # Build the bcftools query format: site fields as %FIELD, per-sample fields inside [...].
        site=""; sample=""
        for f in ~{sep=" " fields}; do
            case "$f" in
                FORMAT/*) sample="${sample}\t%${f#FORMAT/}" ;;
                *) site="${site:+$site\t}%${f}" ;;
            esac
        done
        fmt="${site}${sample:+[$sample]}\n"

        # Split multi-allelic records first so every row has exactly one ALT allele.
        bcftools view ~{if defined(bed) then "--regions-file " + bed else ""} -Ou in.vcf.gz \
            | bcftools norm --multiallelics -any --fasta-ref ref.fa -Ou \
            | bcftools query --print-header -f "$fmt" > raw.tsv
        # Header: drop bcftools' "[1]" column numbers and "#"; values stay as written ("." = missing).
        { head -n1 raw.tsv | sed -e 's/^# *//' -e 's/\[[0-9]*\]//g'; tail -n +2 raw.tsv; } > "~{label}.extract.tsv"

        {
            echo "# Data dictionary for ~{label}.extract.tsv"
            echo
            echo "One row per variant allele inside the requested regions (multi-allelic sites are split"
            echo "into one row per ALT). Missing values are written as \`.\`. Per-sample columns are named"
            echo "\`SAMPLE:FIELD\`."
            echo
            echo "| Column | Type | Description |"
            echo "|---|---|---|"
            for f in ~{sep=" " fields}; do
                case "$f" in
                    CHROM) echo "| CHROM | String | Chromosome |" ;;
                    POS) echo "| POS | Integer | 1-based position of the first REF base |" ;;
                    REF) echo "| REF | String | Reference allele |" ;;
                    ALT) echo "| ALT | String | Alternate allele (one per row) |" ;;
                    QUAL) echo "| QUAL | Float | Phred-scaled variant quality from the caller |" ;;
                    FILTER) echo "| FILTER | String | PASS, or the filters the record failed |" ;;
                    INFO/*|FORMAT/*)
                        kind=${f%%/*}; id=${f#*/}
                        bcftools view -h in.vcf.gz | awk -v k="$kind" -v id="$id" '
                            index($0, "##" k "=<ID=" id ",") == 1 {
                                match($0, /Type=[^,]+/); type = substr($0, RSTART + 5, RLENGTH - 5)
                                match($0, /Description="[^"]*"/); desc = substr($0, RSTART + 13, RLENGTH - 14)
                                printf "| %s | %s | %s |\n", (k == "FORMAT" ? "SAMPLE:" id : id), type, desc; found = 1
                            }
                            END { if (!found) printf "| %s | ? | not declared in the VCF header |\n", id }' ;;
                    *) echo "| $f | ? | |" ;;
                esac
            done
        } > "~{label}.extract.dictionary.md"

        res_t1=$(awk '{print $1}' /proc/uptime)
        printf '{"task":"TargetedTsvExtract","label":"~{label}","wall_seconds":%s,"cpu_seconds":%s,"peak_memory_bytes":%s,"requested_cpu":%s,"requested_memory_gb":%s,"image":"%s"}\n' \
            "$(awk -v a="$res_t0" -v b="$res_t1" 'BEGIN{print b-a}')" \
            "$(awk '/^usage_usec/{print $2/1e6}' /sys/fs/cgroup/cpu.stat 2>/dev/null || echo -1)" \
            "$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo -1)" ~{cpu} ~{memory_gb} "~{docker}" > resources.json
    >>>

    output {
        File tsv = "~{label}.extract.tsv"
        File dictionary = "~{label}.extract.dictionary.md"
        File resources = "resources.json"
    }

    runtime {
        docker: docker
        cpu: cpu
        memory: "~{memory_gb} GiB"
        disks: "local-disk 10 HDD"
    }
}
