# _DEPRECATED_

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