Guidelines and documentation for developers of the SonarQube Docker images.

could not find java in ES_JAVA_HOME
===================================

`could not find java in ES_JAVA_HOME at /usr/lib/jvm/java-11-openjdk/bin/java` is a known error message when the container runtime is too old to be aware of the `faccessat2` syscall.
This issue is tracked with [SONAR-15167](https://jira.sonarsource.com/browse/SONAR-15167) including some worarounds if a update of the container runtime is not possible. 

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


Release process
===============

Go [here](release.md)

Deprecated
==========

More information in [deprecated](deprecated.md) processes/pipelines.