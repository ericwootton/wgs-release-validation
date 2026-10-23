# Working notes for AI assistants (and humans)

Release validation of the germline short-read WGS workflow uses miniwdl to execute WDL 1.0.
Benchmarking is performed using hap.py against GIAB HG002, and validation is gated against
committed baselines.

## Layout

- `wdl/main.wdl` + `wdl/tasks/*.wdl`: Workflow. `wdl/optional/`: Long-read and deliverables modules.
- `scripts/`: Python scripts use the standard library (and PyYAML/matplotlib where noted).
  `fetch_data.py` prepares the data, `summarize_happy.py` generates `metrics.json`, and
  `compare_metrics.py` is the regression gate.
- `config/`: Data manifest (URLs + MD5), profiles (regions), prices, thresholds, and miniwdl settings.
- `baselines/`: Reference metrics used for regression gate decisions. Make changes only as specified in `docs/runbooks/updating-baselines.md`.
- `docs/results/<label>/`: Small generated outputs included in the commit. Large outputs are stored in `results/`.

## Commands

    make test lint                 # pytest, ruff, mypy --strict, miniwdl check, womtool validate
    make run PROFILE=fixture       # offline run on committed test data (minutes)
    make ci                        # ci profile + regression gate
    make run PROFILE=full          # 5 Mb, GATK and DeepVariant

## Rules

- Keep all containers pinned using the `tag@sha256:digest` format. Record all new images in the README tool table.
- Every task writes resource usage (elapsed time, CPU, peak memory) to `resources.json` with the shared snippet. Keep the snippet.
- Never use `samtools reheader` to remove `@SQ` lines. BAM records reference contigs by index.
  Re-encode through SAM text instead (see `FetchReadsSlice`).
- Do not relax the settings in `config/thresholds.yaml` to make the run pass. Investigate and document your findings.
- Never put credentials, account IDs or bucket names in the repo. Cloud configs that contain them are gitignored.
- For Python, use ruff (line length 120), apply mypy in strict mode to `scripts/`, and run the tests in `tests/` offline.
- All numerical results in the documentation are taken from generated files (`metrics.json`,
  `metrics.md`, `gate.md`, `resources.tsv`, and script output). Never enter values manually.
  Reference or embed the generated files, and regenerate them when the inputs change.
- Changes written by an assistant are reviewed as a diff. `make test lint` and any run the change
  affects must pass before it is committed.
