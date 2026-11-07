FROM node:24.14.1-bookworm-slim AS node
FROM python:3.13.15-slim-bookworm
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && pip install --no-cache-dir pytest==9.2.0
RUN useradd --uid 1000 --create-home runner
USER 1000:1000
WORKDIR /workspace
CMD ["python", "--version"]
