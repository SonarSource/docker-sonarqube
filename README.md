# How we use this at Plangrid

The main branch is the `plangrid` branch, and we'll rebase this on top
of the `master` branch when new changes we want come out. Additionally
in the `Jenkinsfile` that is added in this branch, we *cd* directly to
the version we want to deploy, and then build and push the docker image
with tags to our own internal docker registries.

Everything below this line is the original README.md

# About this Repo

This is the Git repo of the official Docker image for [SonarQube](https://registry.hub.docker.com/_/sonarqube/). See the Hub page for the full readme on how to use the Docker image and for information regarding contributing and issues.

The full readme is generated over in [docker-library/docs](https://github.com/docker-library/docs), specifically in [docker-library/docs/sonarqube](https://github.com/docker-library/docs/tree/master/sonarqube).

[![Build Status](https://travis-ci.org/SonarSource/docker-sonarqube.svg)](https://travis-ci.org/SonarSource/docker-sonarqube)
