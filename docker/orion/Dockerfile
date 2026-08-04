# Orion, the unified knowledge plane: one Postgres 18 serving all three
# planes (ADR 0004). Base = official AGE image (AGE is the hard-to-build
# extension — never compile it); pgvector added from PGDG apt.
FROM apache/age:release_PG18_1.7.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-18-pgvector \
    && rm -rf /var/lib/apt/lists/*
