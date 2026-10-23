# Entry points. Run from the repository root on Linux or macOS with Docker and Python 3.10+.
#   make data PROFILE=ci     download GIAB files once, cut them to the profile region
#   make run PROFILE=ci      run the WDL with miniwdl, then copy outputs into results/ and docs/results/
#   make gate PROFILE=ci     compare against the committed baseline (fails on regression)
#   make test lint           unit tests, Python lint and types, WDL validation

PY ?= python3
MINIWDL ?= miniwdl
PROFILE ?= ci
INPUTS ?= inputs/$(PROFILE).json
LABEL ?= $(PROFILE)
BASELINE ?= baselines/$(PROFILE).json
RUNS ?= _runs
WOMTOOL_JAR ?= $(wildcard tools/womtool-*.jar)

.PHONY: data run gate ci run-ci full wes longread sv-merge deliverables deliverables-docs test lint wdl-check cost plots docs docs-latest clean

data:
	$(PY) scripts/fetch_data.py prepare --profile $(PROFILE)

run: data
	mkdir -p $(RUNS)/$(LABEL)
	$(MINIWDL) run wdl/main.wdl -i $(INPUTS) --cfg config/miniwdl.cfg --dir $(RUNS)/$(LABEL) --verbose \
		run_label=$(LABEL) $(EXTRA)
	$(PY) scripts/collect_run.py $(RUNS)/$(LABEL)/_LAST --label $(LABEL)

gate:
	$(PY) scripts/compare_metrics.py $(BASELINE) docs/results/$(LABEL)/metrics.json \
		--out-md docs/results/$(LABEL)/gate.md $(if $(GITHUB_STEP_SUMMARY),--summary-file $(GITHUB_STEP_SUMMARY))

ci: run gate

run-ci: ci

full:
	$(MAKE) run PROFILE=full

# The same profile through a GA4GH WES server (docs/ga4gh.md), gated against the miniwdl run of it.
# WES_FILES is a URL at which the server and its tasks can read this directory.
WES_URL ?= http://localhost:8000/api/ga4gh/wes/v1
WES_FILES ?=
WES_TIMEOUT ?= 3600
wes:
	@test -n "$(WES_FILES)" || { echo "set WES_FILES to a URL that serves this directory" >&2; exit 1; }
	mkdir -p $(RUNS)/wes
	$(PY) scripts/cloud_inputs.py $(INPUTS) --target wes --prefix $(WES_FILES) \
		--out $(RUNS)/wes/$(LABEL).json --uploads $(RUNS)/wes/$(LABEL).uploads.tsv
	$(PY) scripts/wes_run.py --server $(WES_URL) --workflow-url $(WES_FILES)/wdl/main.wdl \
		--params $(RUNS)/wes/$(LABEL).json --out $(RUNS)/wes/$(LABEL) --label $(LABEL) \
		--timeout $(WES_TIMEOUT)
	rm -rf docs/results/$(LABEL)-wes && mkdir -p docs/results/$(LABEL)-wes
	cp $(RUNS)/wes/$(LABEL)/wes_run.json $(RUNS)/wes/$(LABEL)/metrics.json $(RUNS)/wes/$(LABEL)/metrics.md \
		docs/results/$(LABEL)-wes/
	$(PY) scripts/compare_metrics.py docs/results/$(LABEL)/metrics.json docs/results/$(LABEL)-wes/metrics.json \
		--out-md docs/results/$(LABEL)-wes/gate.md

# Optional modules (spec 2.14 and 2.15); run locally, not in CI.
LONGREAD_IDS = stvar_vcf stvar_bed pbsv_trf_bed trgt_catalog strchive_trgt cpg_islands
longread:
	$(PY) scripts/fetch_data.py subset $(LONGREAD_IDS) --profile longread --out data/longread
	mkdir -p $(RUNS)/longread docs/results/longread results/longread
	$(MINIWDL) run wdl/optional/longread.wdl -i inputs/longread.json --cfg config/miniwdl.cfg --dir $(RUNS)/longread --verbose
	tar -xzf $(RUNS)/longread/_LAST/out/handoff_tar/*.tar.gz -C results/longread
	cp results/longread/handoff/QC_SUMMARY.md results/longread/handoff/qc.json results/longread/handoff/MANIFEST.tsv results/longread/handoff/VERSIONS.md docs/results/longread/

# Needs a finished `make longread`: it reuses that run's region-filtered SV VCFs.
sv-merge:
	mkdir -p $(RUNS)/sv-merge
	$(MINIWDL) run wdl/optional/sv_merge.wdl -i inputs/sv_merge.json --cfg config/miniwdl.cfg --dir $(RUNS)/sv-merge \
		--verbose pbsv_vcf=$(RUNS)/longread/_LAST/out/sv_vcfs/0/pbsv.vcf.gz \
		sniffles_vcf=$(RUNS)/longread/_LAST/out/sv_vcfs/1/sniffles.vcf.gz
	$(PY) scripts/sv_merge_report.py $(RUNS)/sv-merge/_LAST --out docs/results/sv-merge

deliverables:
	$(PY) scripts/fetch_data.py subset hg003_vcf hg004_vcf --profile full --out data/deliverables
	mkdir -p $(RUNS)/deliverables
	$(MINIWDL) run wdl/optional/deliverables.wdl -i inputs/deliverables.json --cfg config/miniwdl.cfg --dir $(RUNS)/deliverables --verbose
	$(MAKE) deliverables-docs

# The small, readable deliverables (notes, tables, dictionary) are committed for docs/deliverables.md.
deliverables-docs:
	set -e; o=$(RUNS)/deliverables/_LAST/out; new=docs/results/deliverables.new; \
	rm -rf $$new && mkdir -p $$new; \
	for pair in sites_readme:read-support-slices.md allele_support_tsv:allele-support.tsv \
			collection_readme:collection-vcf.md extract_tsv:extract.tsv extract_dictionary:extract-dictionary.md; do \
		f=$$(find -L $$o/$${pair%%:*} -type f | sort | head -n1); \
		test -n "$$f" || { echo "missing output $${pair%%:*}" >&2; rm -rf $$new; exit 1; }; \
		cp -L "$$f" $$new/$${pair#*:}; \
	done; \
	rm -rf docs/results/deliverables && mv $$new docs/results/deliverables

test:
	$(PY) -m pytest

lint: wdl-check
	$(PY) -m ruff check scripts tests
	$(PY) -m ruff format --check scripts tests
	$(PY) -m mypy scripts

wdl-check:
	$(MINIWDL) check --suppress CommandShellCheck wdl/main.wdl wdl/optional/*.wdl
	@if [ -n "$(WOMTOOL_JAR)" ]; then for f in wdl/main.wdl wdl/optional/*.wdl; do java -jar $(WOMTOOL_JAR) validate $$f || exit 1; done; \
		else echo "womtool jar not found under tools/; skipping womtool validate"; fi

cost:
	$(PY) scripts/estimate_cost.py --results docs/results --prices config/prices.yaml --out docs/results/cost-estimate.md

# Docs site (spec section 7). docs/results/latest/ is generated, never committed.
FROM ?= docs/results/ci
docs-latest:
	rm -rf docs/results/latest && mkdir -p docs/results/latest
	cp $(FROM)/metrics.md $(FROM)/metrics.json docs/results/latest/
	if [ -f $(FROM)/gate.md ]; then cp $(FROM)/gate.md docs/results/latest/; fi
	if [ -n "$(RUN_URL)" ]; then note="From CI run $(RUN_URL)."; \
		else note="From the committed ci results (no CI run available)."; fi; \
		{ echo; echo "$$note"; } >> docs/results/latest/metrics.md

docs: docs-latest
	mkdocs serve

plots:
	$(PY) scripts/plot_metrics.py --metrics full=docs/results/full/metrics.json --out docs/results/figures

clean:
	rm -rf $(RUNS) results
