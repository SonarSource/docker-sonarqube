# Releasing

Overview
--------

Release of a new version of the official SonarQube Docker images is made of several operations:

1. bump the version of SonarQube in Dockerfiles
2. Update the docker hub SonarQube's documentation (if applicable)
3. Update Docker Hub's SonarQube images
4. add a GIT tag for the new version 


Bump the version of SonarQube in Dockerfiles
-----------------------------

The version of SQ is hardcoded in each Dockerfile and must be updated in master branch.


Update the docker hub SonarQube's documentation (if applicable)
-------------------------------

If needed, prepare PR of Docker Hub documentation from SonarSource's fork of [https://github.com/docker-library/docs](https://github.com/docker-library/docs) named [sonarqube-docker-docs](https://github.com/SonarSource/sonarqube-docker-docs)

> Note: updating the fork should not be necessary as we only care about the `sonarqube` directory and are the only people updating it

To create a good PR:

1. The markdown format must follow a certain standard, otherwise automated tests will fail. You can test with the `markdownfmt.sh` tool included in the repository, for example `./markdownfmt.sh -d sonarqube/content.md` will output the diff that would have to be done to make the tests pass. You can use the `patch` command to apply the changes, for example: `./markdownfmt.sh -d sonarqube/content.md | patch sonarqube/content.md`
2. Verify the Pull Request passes the automated tests (visible in the status of the PR)

To control the generated content of the Docker Hub page, look around in the files in `.template-helpers` of the [`docs` repository][docs]. For example, the "Where to get help" section is customized by a copy of `.template-helpers/get-help.md` in `sonarqube/get-help.md`.

Until SonarQube is released and the public artifacts are available, keep your PR a draft PR to make it clear it is not ready to be merged yet.

For more and up to date documentation, see https://github.com/docker-library/docs.


Update Docker Hub's SonarQube images
-----------------------

Update the SonarSource [fork](https://github.com/SonarSource/official-images) of the [official-images](https://github.com/docker-library/official-images) to ensure that the `sonarqube` library is the latest version.

Create a feature branch on the company fork:
* `GitCommit` must be updated to this repository master branch's HEAD.
* `Tags` and `Directory` must be added/updated appropriatly for each edition
* see https://github.com/docker-library/official-images/pull/8837/files as an example

Until SonarQube is released and the public artifacts are available, keep your PR a draft PR to make it clear it is not ready to be merged yet.
* Create the PR [here](https://github.com/docker-library/official-images/compare)
    * If the documentation was updated in the step before, reference that PR in this PR.
* Click on *compare across fork* to be able to use the SonarSource fork as head repository.


For more and up to date documentation, see https://github.com/docker-library/official-images.


Add a GIT tag for the new version 
----------------

The commit referenced in the DockerHub Pull Request must be tagged with the (marketing) version of SQ: eg. `8.0`, `8.0.1`, `8.1`.
