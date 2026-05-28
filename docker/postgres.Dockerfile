# Custom Postgres image for IRIS dev: pgvector + Apache AGE
#
# Base: pgvector/pgvector:pg17 (Debian bookworm, PostgreSQL 17, pgvector pre-installed)
# Adds: postgresql-17-age from the PGDG apt repository (already configured in base)
#
# Apache AGE installation reference:
#   https://hub.docker.com/r/apache/age
#   Ubuntu/Debian: apt-get install postgresql-${PG_MAJOR}-age

FROM pgvector/pgvector:pg17

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       "postgresql-${PG_MAJOR}-age" \
    && rm -rf /var/lib/apt/lists/*

# Init SQL is mounted via compose; extensions are enabled at first boot.
