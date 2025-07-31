# Releasing

## Docker image release cycle and SonarQube Server product

We consider the **docker image** as part of the SonarQube Server **product**. Therefore, it follows the same release process.

## Overview

Release of a new version of the official SonarQube Server Docker images is made of several operations. 

> Please note that steps 1 and 2 are fully automated with [renovate](https://developer.mend.io/). When the SonarQube Server binaries are made available, please activate the Renovate scan to trigger a new release (i.e., `docker-sonarqube` -> `Actions` -> `Run Renovate Scan`).

1. Set the new version of SonarQube Server (`SONARQUBE_VERSION`) to be released in the Dockerfiles. In case of community build, please remember to update `community-build/Dockerfile` only.
2. Set the new version in `.cirrus/tasks.yml`. If you are releasing a new LTA, set `CURRENT_VERSION` in `.cirrus/tasks.yml` on the related lta branch. Otherwise, if you are releasing a Community build, set `COMMUNITY_BUILD_VERSION` only. In all the other cases where a paid edition is about to be releases, set `CURRENT_VERSION` (please note that the nightly build will fail before the public image becomes available).
3. Update the docker hub SonarQube Server's documentation (if applicable)
4. Update Docker Hub's SonarQube Server images
5. Add a GIT tag for the new version (This needs to be done after the images become available on DockerHub)
   1. If you are releasing a SonarQube Server version, you need to [Add a New Release](https://github.com/SonarSource/docker-sonarqube/releases/new), where the name matches "SonarQube Server", followed by the release version, e.g., "SonarQube Server 2025.1.0".
   2. Likewise, if you are releasing a Community Build, the release name should match "Community Build", followed by the release version, e.g., "Community Build 25.1.0.102122".
   3. The Git tag for the SonarQube Community Build release must be the full version, e.g., `25.1.0.102122`.

## Bump the version of SonarQube Server in Dockerfiles

The version of SonarQube Server is hardcoded in each Dockerfile of this repository and must be updated in master branch.

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

* `GitCommit` must be updated to this repository master branch's HEAD.
* `GitFetch` is the branch/tag (e.g., refs/tags/10.8.1) where the commit can be found. Setting this value is only needed if you are releasing from a branch different from master.
* `Tags` and `Directory` must be added/updated appropriately for each edition

Please check the https://github.com/docker-library/official-images/pull/8837/files as an example.

> In the future, also åthe folliwing steps will be also automated through github actions.

Until SonarQube Server is released and the public artifacts are available, keep your PR a draft PR to make it clear it is not ready to be merged yet.

* Create the PR [here](https://github.com/docker-library/official-images/compare)
  * If the documentation was updated in the step before, reference that PR in this PR.
* Click on *compare across fork* to be able to use the fork as head repository.

For more and up to date documentation, see https://github.com/docker-library/official-images.

## Add a GIT tag for the new version

The commit referenced in the DockerHub Pull Request must be tagged with the (marketing) version of SQ: eg. `8.0`, `8.0.1`, `8.1`.
