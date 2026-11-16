# Docker Compose Examples

This directory contains Docker Compose examples for running SonarQube Server in different configurations.

To deploy SonarQube Server with the agentic components (Agent Orchestrator, Hunter, Remediation and Vortex), use the [agentic compose generator](../agentic-compose-generator/) instead: it generates a complete bundle for your edition, storage and TLS setup.

## ⚠️ Known Issue with DCE Examples

**The DCE examples (`sq-dce-postgres` and `sq-dce-custom-zip-postgres`) will not work with the current images until the next release.**

The health checks in these compose files rely on `curl`, but the currently released search images do not include (curl) it. This causes health checks to fail and prevents the containers from starting properly.

**Workarounds:**
- **Wait for the next release** - upcoming images will include `curl` and work out of the box
- **Rebuild the search image locally** - the current Dockerfile already includes `curl`, so rebuilding from source will produce a working image

We are aware of this issue and it will be resolved in the next official release.

## Upgrading the PostgreSQL database

The `sq-with-postgres`, `sq-dce-postgres` and `sq-dce-custom-zip-postgres` examples use `postgres:17` and keep the database in the `postgresql_data` volume.

A database created by an older PostgreSQL major version doesn't start on a newer one ("database files are incompatible with server"). For a throwaway setup, run `docker compose down -v` to start over. To keep the data, dump it with the previous compose file and restore it with the new one:

```bash
docker compose exec -T db pg_dumpall -U sonar > sonar.sql   # previous compose file
docker compose down
docker volume rm <project>_postgresql_data
# switch to the new compose file
docker compose up -d db
docker compose exec -T db psql -U sonar -d postgres < sonar.sql
docker compose up -d
```

### Recovering data from an anonymous volume

Earlier versions of `sq-with-postgres` and `sq-dce-postgres` mounted the named volume on `/var/lib/postgresql`, so the database was written to an anonymous volume. To recover it, find the volume (`docker run --rm -v <volume>:/v alpine cat /v/PG_VERSION` prints the major version), dump it with a temporary container of that version, then restore as above:

```bash
docker run -d --name pg-old -v <anonymous-volume>:/var/lib/postgresql/data postgres:<major-version>
docker exec pg-old pg_dumpall -U sonar > sonar.sql
docker rm -f pg-old
```

The old `<project>_postgresql` volume is no longer used and can be removed.
