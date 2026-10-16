FROM python@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170
RUN groupadd --gid 10001 aie && useradd --uid 10001 --gid 10001 --create-home --shell /bin/bash aie
ENV HOME=/home/aie PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
ENV PATH=/opt/aie-tools:/usr/local/bin:/usr/bin:/bin
USER 10001:10001
WORKDIR /workspace
ENTRYPOINT ["python", "-B", "/control/tools/container_native_probe.py"]
