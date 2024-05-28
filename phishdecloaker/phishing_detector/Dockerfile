FROM mambaorg/micromamba@sha256:76220befc2349e1a050387255ba1970d6770644629fc7ebe54ac73e367a369b0
USER root
RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends --reinstall \
    libgl1 \
    libglib2.0-0 \
    libgl1-mesa-glx \
    curl
COPY --chown=$MAMBA_USER:$MAMBA_USER ./environment.yml /tmp/environment.yml
RUN micromamba install -y -n base -f /tmp/environment.yml && \
    micromamba clean --all --yes
ARG MAMBA_DOCKERFILE_ACTIVATE=1
WORKDIR /detector
COPY . .
EXPOSE 8000
CMD ["python", "-u", "detector.py"]