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

## PostgreSQL version and upgrades

The `sq-with-postgres`, `sq-dce-postgres` and `sq-dce-custom-zip-postgres` examples run `postgres:18` by default. To run another supported major version (15 to 18), add it to a `.env` file next to the compose file, so every `docker compose` command uses it (for example `POSTGRES_VERSION=17`).

The database is kept in the `postgresql_data` volume, mounted on `/var/lib/postgresql`, in a `<major-version>/docker` subdirectory. Versions 15 to 17 also create an empty, unused anonymous volume for `/var/lib/postgresql/data` each time the container is created.

If you ran an earlier version of these examples, move your database to the new layout before updating, then optionally upgrade it to 18:

- `sq-dce-custom-zip-postgres`: until you do, the `db` container exits with `there appears to be PostgreSQL data in`.
- `sq-with-postgres` and `sq-dce-postgres`: there is no error. The new compose file starts with an empty database, and your data stays in an anonymous volume no longer used by any container. Don't run `docker volume prune`.

For a throwaway setup, run `docker compose down -v` to start over instead.

### Moving an existing database to the new layout

This keeps your current PostgreSQL major version, without a dump. Stop the stack with the previous compose file, then find where your database is:

- `sq-dce-custom-zip-postgres`, and other examples mounting `postgresql_data` on `/var/lib/postgresql/data`: at the root of the `<project>_postgresql_data` volume.
- `sq-with-postgres` and `sq-dce-postgres` mounting a `postgresql` volume on `/var/lib/postgresql`: in an anonymous volume. Before stopping the stack, `docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}' <db-container>` prints its name. If you already updated, look for it in `docker volume ls -qf dangling=true`. The old `<project>_postgresql` volume only holds an empty `data` directory.

`cat PG_VERSION` at the root of either volume prints the major version. Switch to the new compose file, set that version in `.env`, then move the database (if your database is in an anonymous volume and you already started the new compose file, first remove the empty database it created with `docker compose down` and `docker volume rm <project>_postgresql_data`):

```bash
# .env: POSTGRES_VERSION=<major-version>
# database in <project>_postgresql_data:
docker run --rm -v <project>_postgresql_data:/v alpine sh -c \
  'cd /v && V=$(cat PG_VERSION) && for d in */docker; do rmdir "$d" "${d%/docker}" 2>/dev/null; done; mkdir .move && mv $(ls -A | grep -vx .move) .move/ && mkdir $V && mv .move $V/docker'
# database in an anonymous volume:
docker compose create db
docker run --rm -v <anonymous-volume>:/from -v <project>_postgresql_data:/v alpine sh -c \
  'V=$(cat /from/PG_VERSION) && mkdir -p /v/$V/docker && cp -a /from/. /v/$V/docker/'
docker compose up -d
```

### Upgrading to a newer major version

PostgreSQL doesn't start on a database created by another major version, and refuses to create a new one next to it in the volume. Dump the database, move the old one aside, then restore the dump on the new version:

```bash
docker compose exec -T db pg_dumpall -U sonar > sonar.sql
docker compose down
docker run --rm -v <project>_postgresql_data:/v alpine sh -c 'mv /v/<old-version>/docker /v/<old-version>-backup && rmdir /v/<old-version>'
# .env: POSTGRES_VERSION=18, or remove it
docker compose up -d --wait db
docker compose exec -T db psql -U sonar -d postgres < sonar.sql
docker compose up -d
```

Once SonarQube Server works on the new version, remove the backup with `docker run --rm -v <project>_postgresql_data:/v alpine rm -rf /v/<old-version>-backup`.
