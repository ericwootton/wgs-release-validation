# hap.py 0.3.15 with RTG Tools 3.13, so `hap.py --engine vcfeval` works.
#
# The bioconda hap.py package builds with has_vcfeval = 0 and does not install rtg, so the
# stock biocontainers image fails with `--engine vcfeval`. This copies RTG Tools (and the Java
# runtime bundled with it) from its own biocontainer into /opt/rtg and points rtg.cfg there.
FROM quay.io/biocontainers/rtg-tools:3.13--hdfd78af_0@sha256:6a85ea03bdb8b30ae6a10f01e9eb0a35dd0dcf66438d988dd5f65e11786b6d98 AS rtg

FROM quay.io/biocontainers/hap.py:0.3.15--py27hcb73b3d_0@sha256:d63b963a6cb01b4830393b22369e7b91d298e4156dde353739e74e4cfa4f96d0
COPY --from=rtg /usr/local /opt/rtg
RUN cfg=/opt/rtg/share/rtg-tools-3.13-0/rtg.cfg \
    && sed -i 's#RTG_JAR=/usr/local/#RTG_JAR=/opt/rtg/#; s#RTG_JAVA=/usr/local/bin/java#RTG_JAVA=/opt/rtg/bin/java#; s#RTG_TALKBACK=true#RTG_TALKBACK=false#' "$cfg" \
    && ln -s /opt/rtg/bin/rtg /usr/local/bin/rtg \
    && rtg version | head -1
LABEL org.opencontainers.image.description="hap.py 0.3.15 + RTG Tools 3.13 (vcfeval engine)"
