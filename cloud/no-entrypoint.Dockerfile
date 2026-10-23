# HealthOmics runs each task's command as an injected bash script and expects images without an
# ENTRYPOINT (docs/results/cloud-run.md). The biocontainers images, and happy-vcfeval built on
# one, set ENTRYPOINT ["/usr/local/env-execute"]. This clears it and changes nothing else:
#
#   docker build -f cloud/no-entrypoint.Dockerfile --build-arg BASE=<image@digest> -t <ecr uri> cloud
ARG BASE
FROM ${BASE}
ENTRYPOINT []
CMD ["/bin/bash"]
