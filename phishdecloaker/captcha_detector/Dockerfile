FROM mambaorg/micromamba@sha256:b21ec7d174b2a907e228722fc5b7a36b4900597073d046517185db196a4a8625
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
WORKDIR /captcha_detector
COPY . .
EXPOSE 8000
CMD ["python", "-u", "app.py"]