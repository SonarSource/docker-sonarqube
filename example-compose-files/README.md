# Docker Compose Examples

This directory contains Docker Compose examples for running SonarQube Server in different configurations.

## ⚠️ Known Issue with DCE Examples

**The DCE examples (`sq-dce-postgres` and `sq-dce-custom-zip-postgres`) will not work with the current images until the next release.**

The health checks in these compose files rely on `curl`, but the currently released search images do not include (curl) it. This causes health checks to fail and prevents the containers from starting properly.

**Workarounds:**
- **Wait for the next release** - upcoming images will include `curl` and work out of the box
- **Rebuild the search image locally** - the current Dockerfile already includes `curl`, so rebuilding from source will produce a working image

We are aware of this issue and it will be resolved in the next official release.

## Starting the DCE examples

On a fresh database the first application node initializes the schema, so the application nodes must
not start at the same time. The compose files enforce the order with `depends_on`, and the health
checks give the first node time to migrate. Start the cluster with:

```
docker compose up -d --wait
```

`--wait` brings the nodes up in dependency order and waits for each to become healthy.