FROM mambaorg/micromamba:latest
USER root
COPY --chown=$MAMBA_USER:$MAMBA_USER ./environment.yml /tmp/environment.yml
RUN micromamba install -y -n base -f /tmp/environment.yml && \
    micromamba clean --all --yes
ARG MAMBA_DOCKERFILE_ACTIVATE=1
WORKDIR /filter
COPY . .
CMD ["python", "-u", "filter.py"]