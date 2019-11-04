Guidelines and documentation for developers of the SonarQube Docker images.


Adding images for a new version of SQ
=====================================

New major version
-----------------

Create a new subdirectory with the major version number in the root directory of the repository with a sub directory for each supported edition, eg.: 

```
mkdir -p 9/community 9/developer 9/enterprise
```

Each edition directory will contain a single Dockerfile.

New non-major version
---------------------

As of today, we publish only a single version of SQ for a given major version in the "master" branch.

No new image is therefor created for non-major versions of SQ. Instead, existing images are updated.

Docker images of older intermediate versions are accessible via tags.


Dogfooding and images for local artifacts
=========================================

Dogfooding
----------

SonarQube Docker images are dogfooded.

This implies that Docker images are produced for every artifact produced from the dogfood branch of SonarQube (see the [dogfood_docker_build_task](https://github.com/SonarSource/sonar-enterprise/blob/master/.cirrus.yml#L263)).

Docker images of SonarQube are built from publicly available artifacts, which means the Dockerfile can simply download them from the public place they are hosted (`binaries.sonarsource.com`).

However, this is not the case for artifacts built from the dogfood branch, which are private.

At some point of time, Dockerfile add the ability to download from the private hosting. Credentials where provided as `docker build` arguments. This option was **dropped because it was leaking credentials into the Docker image layers**.

Instead, the download is now performed by the [`build-docker-from-private-repo.sh`](8/build-docker-from-private-repo.sh) script which then relies on the Dockerfile ability to bundle any locally provided SQ artifact (see below).

Local artifacts
---------------

Dockerfile supports creating image from any locally provided SQ artifact.

This artifact should be named `sonarqube-${SONARQUBE_VERSION}.zip` and located in the `zip` directory of the `docker build` context. If such file exists, this artifact will be used to build the image instead of downloading it from `binaries.sonarsource.com`.

Note that:

1. there is no check to enforce version of SQ in the zip file matches the `docker build` argument
	* this is, by the way, used and exploited in dogfooding where Docker images for 8.0 are used to build images of 8.1 currently under development
2. this feature must be removed from the official Dockerfile published to Docker Hub (see "Release process" below).


ITs
===

ITs run on Travis, see [.travis.yml](.travis.yml).

Currently, ITs are "simply" building a given image of SonarQube and make sure they can run it and have SonarQube responding on HTTP calls in a reasonable time.

Since 8.0, images offer more features which are unfortunately not tested automatically (eg. `--init` parameter and automatice initialization of mounted directories).


Release process
===============

Release of a new version of the official SonarQube Docker images is made of several operations:

1. create or update the "version branch"
2. bump the version of SonarQube in Dockerfiles
3. have the new docker images published on Docker Hub
4. add a GIT tag for the new version

Surprisingly, the third operation can and even should be prepared before the two first operations are done. The reason is that involves opening up to two Pull Requests (see below) to Docker Hub which review can take some time.

create/update the "version branch"
----------------------------------

A specific branch must be created from which official images will be published, let's call it the "version branch".

Official images can not be published from master as some dev-related code must be removed from the official images (see below).

The "version branch" is named `branch-[version]`, eg.: `branch-8`.

### new major version

Create the "version branch" from master and remove dev-specific code from it (see below).

### new non-major version

Merge master into the existing "version branch" in case some developement occured on the Docker images. Make sure no dev-specific is added to it.

### clean the "version branch"

In the "version branch", all code related to the local artifact support must be removed from the Dockerfiles:

* this feature is not welcome in official images (see https://github.com/docker-library/official-images/pull/6778#issuecomment-541976967)
* as an example, see [commit](https://github.com/SonarSource/docker-sonarqube/commit/8ae0fadc72fef64334998e811f1b9cf68a458a2c) which is, unfortunately, missing the removal of `&& rm -Rf "${SONARQUBE_ZIP_DIR}" \`


bump the version of SonarQube
-----------------------------

The version of SQ is hardcoded in each Dockerfile and must be updated in master and then merged into the "version" branch.

In the "version branch", ITs must be updated to build and test the images from public artifacts, see as an example this [commit](https://github.com/SonarSource/docker-sonarqube/commit/8ae0fadc72fef64334998e811f1b9cf68a458a2c).

Of course, these changes should only be made after the release of the SonarQube artifacts.


Update Docker Hub image
-----------------------

Prepare PR of Docker Hub images from a fork of [https://github.com/docker-library/official-images](https://github.com/docker-library/official-images)

* until now, this fork has been a developer-private one shared add-hoc with other developers
* `GitFetch` must be updated/set to point to the "version branch"
* `GitCommit` must be updated to the HEAD of the "version branch"
* `Tags` and `Directory` must be added/updated appropriatly for each edition
* see https://github.com/docker-library/official-images/pull/6778/files as an example

Until SonarQube is released and the public artifacts are available, keep your PR a draft PR to make it clear it is not ready to be merged yet.

For more and up to date documentation, see https://github.com/docker-library/official-images.


Update Docker Hub documentation
-------------------------------

If needed, prepare PR of Docker Hub documentation from SonarSource's fork of [https://github.com/docker-library/docs](https://github.com/docker-library/docs) named [sonarqube-docker-docs](https://github.com/SonarSource/sonarqube-docker-docs)

> Note: updating the fork should not be necessary as we only care about the `sonarqube` directory and are the only people updating it

To create a good PR:

1. The markdown format must follow a certain standard, otherwise automated tests will fail. You can test with the `markdownfmt.sh` tool included in the repository, for example `./markdownfmt.sh -d sonarqube/content.md` will output the diff that would have to be done to make the tests pass. You can use the `patch` command to apply the changes, for example: `./markdownfmt.sh -d sonarqube/content.md | patch sonarqube/content.md`
2. Verify the Pull Request passes the automated tests (visible in the status of the PR)

To control the generated content of the Docker Hub page, look around in the files in `.template-helpers` of the [`docs` repository][docs]. For example, the "Where to get help" section is customized by a copy of `.template-helpers/get-help.md` in `sonarqube/get-help.md`.

Until SonarQube is released and the public artifacts are available, keep your PR a draft PR to make it clear it is not ready to be merged yet.

For more and up to date documentation, see https://github.com/docker-library/docs.

Create a GIT tag
----------------

The commit referenced in the DockerHub Pull Request must be tagged with the version of SQ: eg. `8.0`, `8.0.1`, `8.1`.

Discussion around the "version branch"
======================================

The "version branch" has been introduced as a mean to comply with two opposing constraints:

1. to not have code in Dockerfile which is useless and only developement/dogfood specific
2. use the real images for dogfooding

This solution is not great:

* it implies multiple manual operations for each release with a high risk of mistake
* we are not sure how convenient it will be for next releases

However, given the time constraints at the time, it was a good choice: it worked and was very quick and quite low risk to implement.

Alternative
-----------

One promising alternative has been discussed.

Based on the observation that:

1. edition Dockerfiles vary by hardly more than a URL from each other
2. the official image is basically the dev image stripped from some identifed code

The idea would be to have:

1. 6 Dockerfiles commit into the repository: two per editions, one for official image (no dev-specific code) and one for dev/dogfooding
2. a Dockerfile "template"
3. a script responsible for generating the 6 Dockerfiles from the "template"
4. an IT ensuring that the 6 Dockerfiles are up to date with the "template" and the script (to prevent dev from forgetting to commit up-to-date Dockerfiles)

With this idea:

1. trust in dogfooding Docker images representatives of the one which will end up as the official images moves from the developer doing the right changes when cleaning the "version" branch to the script and the template
  * no more human based last minute changes is an obvious improvement
  * it's all commited so an error is easy to track
2. there is no longer a need for a "version" branch

However, it requires some time to develop and even confirm it's just feasible. For these reasons, this option wasn't retained at the time.