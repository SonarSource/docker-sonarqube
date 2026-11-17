# Releasing

## Docker image release cycle and SonarQube Server product

We consider the **docker image** as part of the SonarQube Server **product**. Therefore, it follows the same release process.

## Overview

Release of a new version of the official SonarQube Server Docker images is made of several operations. 

1. Prepare and merge the version bump PR into the intended source branch.
2. Validate the release commit, including image tests and security scans.
3. Update Docker Hub documentation if needed.
4. Submit the official-images PR for that commit and wait for the images to become available on Docker Hub.
5. Publish the GitHub release and tag for the same commit. Commercial releases trigger GCP production image promotion and its release gate.

## Prepare the version bump PR

Use the intended `release/X.Y` branch for a release from a maintained release line, rather than assuming `master` is the source. Use `master` for releases prepared there. For Community Build, use the automation described below.

Check `baseBranches` and the matching rules in [renovate.json5](renovate.json5) before relying on Renovate. The current configuration lists selected release branches (`release/2025.1` and `release/2025.4`), not every `release/X.Y` branch. Where configured, select `docker-sonarqube` in the [Mend developer portal](https://developer.mend.io/) and use **Actions > Run Renovate Scan** after the binaries become available. If Renovate does not cover the intended branch or version locations, open a manual bump PR against that branch.

For a commercial release, review and update these locations together:

- `SONARQUBE_VERSION` in `commercial-editions/developer/Dockerfile`, `commercial-editions/enterprise/Dockerfile`, `commercial-editions/datacenter/app/Dockerfile`, and `commercial-editions/datacenter/search/Dockerfile`. Use the full binary version and update the corresponding download checksum where present.
- `versions.current` in `.github/github_env.yaml`. For an LTA release, update it on the corresponding LTA release branch. Nightly builds can fail until the public images become available.
- Applicable version defaults in `agentic-compose-generator/default-images.json`.
- Applicable image tags in `example-compose-files/`.

### Community Build automation

Use [Community Build Version Bump](.github/workflows/community-build-version-bump.yml), triggered by the `sonarqube-community-build-released` repository dispatch or run manually with `community_build_version` and the `jira_key` for the release. It opens a PR against the default branch to update `community-build/Dockerfile` and `versions.community_build` in `.github/github_env.yaml`. Leave the commercial version fields unchanged. Review applicable examples separately.

Preserve the generated branch name `task/REL-N-bump-community-build-version-VERSION` and the `community-build-release` label. When that PR merges into `master`, [Community Build Release on Merge](.github/workflows/community-build-release-on-merge.yml) creates the draft GitHub release targeting the merge commit. It also dispatches `community-build-release.yml` in `SonarSource/helm-chart-sonarqube` with `community_build_number` and `jira_key`.

A Renovate or manual bump PR without the required branch name and label does not trigger these steps. In that case, the release operator must prepare the draft release for the intended commit and arrange the Helm chart release dispatch separately. Draft creation does not publish the release: confirm Docker Hub availability before publication as described below.

### Handle base-image scan findings

Do not add package-upgrade commands to the dependent Dockerfiles to clear findings inherited from the base image. Docker Official Images require reproducible builds. First check whether a refreshed upstream base image supplies the fix, and validate that base on the release branch.

If a temporary exception is justified, submit a reviewed change to `.trivyignore.yaml` on the release branch. Each entry needs the vulnerability `id`, a `statement` that names the owner and explains the justification, and an `expired_at` date. Record the affected package, reachability evidence, and the planned fix or upstream update in the justification. A failing scan alone does not justify an exception.

Choose an expiry that meets the applicable remediation SLA. Reassess or remove the exception before it expires; do not extend it without new evidence and review. An expired exception no longer suppresses the finding. The scan and CVSS policy evaluation must pass before release and production promotion; do not bypass the gate.

Validate image tests and scan results on both `linux/amd64` and `linux/arm64`. The base-image package versions can differ between architectures, so a passing result on one architecture does not establish that the other passes. The current CI Trivy jobs and GCP production release gate scan on amd64 runners; they do not establish arm64 scan coverage.

For each affected edition image tag, run Trivy separately with `--platform linux/amd64` and `--platform linux/arm64`. Use `--config .github/trivy.yaml`, `--ignorefile .trivyignore.yaml`, `--ignore-unfixed`, `--show-suppressed`, `--severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL`, and `--format json`. Save each architecture's report separately. Run `.github/workflows/scripts/evaluate-trivy-report.py` with each report using Python 3, as the CI jobs do. Retain both scan reports and policy results with the release evidence. Both results must pass; the automated amd64 gate does not replace this arm64 validation.

### GCP staging builds

[push_and_pr.yml](.github/workflows/push_and_pr.yml) rebuilds the GCP staging app and search images after the image tests on qualifying pushes to `master` and `release/*`. Patch releases do not need a temporary staging branch.

The push trigger has path filters for image sources, selected workflow and scan configuration, `run-tests.sh`, and `docker-official-images/`. Check the workflow's `on.push.paths` list for the exact scope. A documentation-only push, or another push outside those paths, does not trigger a staging rebuild.

## Update the docker hub SonarQube Server's documentation (if applicable)

If needed, prepare PR of Docker Hub documentation [https://github.com/docker-library/docs](https://github.com/docker-library/docs).

> Note: Please use your own fork like seen in [this closed PR](https://github.com/docker-library/docs/pull/1660)

To create a good PR:

1. The markdown format must follow a certain standard, otherwise automated tests will fail. You can test with the `markdownfmt.sh` tool included in the repository, for example `./markdownfmt.sh -d sonarqube/content.md` will output the diff that would have to be done to make the tests pass. You can use the `patch` command to apply the changes, for example: `./markdownfmt.sh -d sonarqube/content.md | patch sonarqube/content.md`
2. Verify the Pull Request passes the automated tests (visible in the status of the PR)

To control the generated content of the Docker Hub page, look around in the files in `.template-helpers` of the [`docs` repository][docs]. For example, the "Where to get help" section is customized by a copy of `.template-helpers/get-help.md` in `sonarqube/get-help.md`.

Until SonarQube Server is released and the public artifacts are available, keep your PR a draft PR to make it clear it is not ready to be merged yet.

For more and up to date documentation, see https://github.com/docker-library/docs.

## Update Docker Hub's SonarQube Server images

In order to update the Docker Hub images, a Pull Request must be created on the [official-images](https://github.com/docker-library/official-images) repository. You can use your own personal fork or SonarSource's fork. The manifest (`library/sonarqube`) needs to be update in the following sections before opening a new PR.

> The following steps can be automated using the go-tool described [here](./docker-official-images/README.md). This tool generates a `docker-official-images/official_images.txt` from all the versions in `docker-official-images/active_versions.json`.

You need to update:

* `GitCommit` must identify the validated HEAD of the actual source branch in this repository, for example `release/X.Y`.
* `GitFetch` identifies the branch or tag where that commit can be fetched. For a release branch, use `refs/heads/release/X.Y`. It is needed when the source differs from `master`.
* `Tags` and `Directory` must be added/updated appropriately for each edition

Please check the https://github.com/docker-library/official-images/pull/8837/files as an example.

If the release branch advances after you open the official-images PR, validate the new head and update `GitCommit` in that PR. Update the target of the draft GitHub release to the same intended head before publication. Recheck that both references identify the exact commit that Docker Hub will build.

Until SonarQube Server is released and the public artifacts are available, keep your PR a draft PR to make it clear it is not ready to be merged yet.

* Create the PR [here](https://github.com/docker-library/official-images/compare)
  * If the documentation was updated in the step before, reference that PR in this PR.
* Click on *compare across fork* to be able to use the fork as head repository.

For more and up to date documentation, see https://github.com/docker-library/official-images.

## Publish the GitHub release and tag

Wait for official-images publication and confirm that all intended edition tags and architectures are available on Docker Hub. A merged official-images PR alone does not prove that image publication has finished.

Create or update the [draft GitHub release](https://github.com/SonarSource/docker-sonarqube/releases/new). Its target must be the exact commit referenced by `GitCommit` in the official-images PR. If the release branch moved, reconcile both references and validate the intended head before publishing. Do not tag a different commit merely because it is now the branch head.

- For SonarQube Server, use the marketing version as the tag, for example `2026.5.5`, and name the release `SonarQube Server 2026.5.5`.
- For Community Build, use the full version as the tag, for example `26.11.0.134175`, and name the release `SonarQube Community Build 26.11.0.134175`. The `SonarQube Community Build` prefix lets the release workflow exclude it from commercial GCP promotion.

Publish only after Docker Hub availability is confirmed. Publishing a commercial GitHub release triggers [release.yml](.github/workflows/release.yml), which promotes the Data Center app and search images from Docker Hub to GCP production through [gcp-build-template.yml](.github/workflows/gcp-build-template.yml). That template re-scans the amd64 variant of each Data Center component image and evaluates the CVSS policy before the production push. It does not scan arm64; complete the separate architecture validation above before release. Monitor the release gate and promotion jobs; do not bypass a failed gate. Community Build release publication skips these commercial production jobs.
