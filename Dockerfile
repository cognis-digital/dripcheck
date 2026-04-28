FROM python:3.12-slim
LABEL org.opencontainers.image.title="cognis-dripcheck"
LABEL org.opencontainers.image.source="https://github.com/cognis-digital/dripcheck"
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir .
ENTRYPOINT ["dripcheck"]
