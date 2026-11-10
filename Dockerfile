# syntax=docker/dockerfile:1
# ==============================================================================
# Dockerfile — ai-agent
# ==============================================================================
# Multi-stage build: `builder` installs the Python dependencies into a virtual
# environment; `production` copies that environment and the files the service
# reads at run time onto a slim, non-root base. Built and pushed with
# target: production (.github/workflows/~step-4-build.yml).
#
# What the service needs at run time (docs/deployment/deployment.md): the code
# (application, composition_root, domain, infrastructure) and the files it reads
# when it starts or answers (config, flows, mcps, model_sets, profiles, prompts,
# schema, step_defs). Not tests, docs, scripts, the local venv or any .env.
#
# The two wheels in vendor/ (contracts and shared-logging) are installed from
# requirements.txt: the build needs no sibling checkout.
# ==============================================================================

ARG PYTHON_VERSION=3.14

# ------------------------------------------------------------------------------
# STAGE: builder
# ------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /src

RUN python -m venv /opt/venv

# Only what the install needs, so a code change does not reinstall the packages.
COPY requirements.txt ./
COPY vendor ./vendor

RUN /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ------------------------------------------------------------------------------
# STAGE: production (last, so it is also the default target)
# ------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS production

# PYTHONDONTWRITEBYTECODE: the root filesystem is read-only in the cluster.
# AI_AGENT_RELOAD=0: no auto-reload (the default is 1, for development).
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AI_AGENT_RELOAD=0

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

COPY application ./application
COPY composition_root ./composition_root
COPY domain ./domain
COPY infrastructure ./infrastructure
COPY config ./config
COPY flows ./flows
COPY mcps ./mcps
COPY model_sets ./model_sets
COPY profiles ./profiles
COPY prompts ./prompts
COPY schema ./schema
COPY step_defs ./step_defs

# Numeric, so the kubelet can verify runAsNonRoot; uid 65534 is `nobody`.
USER 65534:65534

# Documentation only: the real address is HTTP_ADDR (the deploy sets it).
EXPOSE 7998

ENTRYPOINT ["python", "composition_root/main.py"]
