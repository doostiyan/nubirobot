FROM python:3.8 AS base

WORKDIR /backend

RUN apt-get update && apt-get install --no-install-recommends  -y \
  automake \
  build-essential \
  cmake \
  libffi-dev \
  libpq-dev \
  libsecp256k1-dev \
  libtool \
  pkg-config \
  python3-virtualenv \
  python3-dev \
  python3-setuptools \
  python3-pip python3-smbus \
  python3-openssl \
  software-properties-common \
  zlib1g \
  zlib1g-dev \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN python3 -m venv $VIRTUAL_ENV
RUN pip3 install --upgrade pip setuptools wheel

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
  pip3 install -r requirements.txt

COPY requirements-prod.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
  pip3 install -r requirements-prod.txt

FROM base AS base-dev
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
COPY requirements-dev.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
  pip install -r requirements-dev.txt

FROM python:3.8-slim AS prod
RUN adduser --system --no-create-home user
RUN apt-get update && apt-get install --no-install-recommends -y \
  curl \
  libmagic1 \
  libxml2 \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv
COPY --from=base $VIRTUAL_ENV $VIRTUAL_ENV
COPY . /backend
WORKDIR /backend
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# check every 5s to ensure this service returns HTTP 200
HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -fs -XPOST http://127.0.0.1:8000/check/health | jq -e '.status != "failed"' > /dev/null || echo "Health check failed"

RUN chmod +x ./scripts/serve.sh
USER user
ENTRYPOINT ["./scripts/serve.sh"]

FROM prod as dev
ENV VIRTUAL_ENV=/opt/venv
COPY --from=base-dev $VIRTUAL_ENV $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
USER root
RUN chmod +x ./scripts/serve-dev.sh
USER user
CMD ["./scripts/serve-dev.sh"]
