
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://assets-eu-01.kc-usercontent.com/ef593040-b591-0198-9506-ed88b30bc023/a23fc7ba-23f0-489a-829d-ed88c0748521/Sonar_Logo_Dark%20Backgrounds.svg">
    <img src="https://assets-eu-01.kc-usercontent.com/ef593040-b591-0198-9506-ed88b30bc023/82c13eba-d95c-4bb8-8007-7ce77c14e043/Sonar_Logo_Light%20Backgrounds.svg" alt="Sonar logo" width="400">
  </picture>
</p>

# SonarQube Docker images

<p>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://assets-eu-01.kc-usercontent.com/ef593040-b591-0198-9506-ed88b30bc023/19f97554-c5ec-4cf1-87f7-878c02a19702/SQ_Logo_Server_Dark%20Backgrounds.svg">
    <img src="https://assets-eu-01.kc-usercontent.com/ef593040-b591-0198-9506-ed88b30bc023/4a785d22-7141-409d-95a2-695c42595f90/SQ_Logo_Server_Light%20Backgrounds.png" alt="SonarQube Server logo" width="400">
  </picture>
</p>

Run a self-managed SonarQube instance in a container and make code quality and security analysis available to local and CI workflows.

[![CI - Build and Test](https://github.com/SonarSource/docker-sonarqube/actions/workflows/push_and_pr.yml/badge.svg)](https://github.com/SonarSource/docker-sonarqube/actions/workflows/push_and_pr.yml) [![Quality Gate Status](https://next.sonarqube.com/sonarqube/api/project_badges/measure?project=SonarSource_docker-sonarqube_AYcnOvlJTpBOcQuGEdI5&metric=alert_status&token=sqb_352337cc82cd0ba5dd1026de82ff553dd511afc2)](https://next.sonarqube.com/sonarqube/dashboard?id=SonarSource_docker-sonarqube_AYcnOvlJTpBOcQuGEdI5)
[![Docker pulls](https://img.shields.io/docker/pulls/library/sonarqube)](https://hub.docker.com/_/sonarqube)
[![GitHub stars](https://img.shields.io/github/stars/SonarSource/docker-sonarqube?style=flat)](https://github.com/SonarSource/docker-sonarqube)
[![License](https://img.shields.io/badge/license-LGPL--3.0-blue)](#license)
[![Community forum](https://img.shields.io/badge/community-forum-blue)](https://community.sonarsource.com/)

About this Repo
-----------------

This is the Git repo of the official Docker image for [SonarQube](https://registry.hub.docker.com/_/sonarqube/). See the Hub page for the full readme on how to use the Docker image and for information regarding contributing and issues.

The full readme is generated over in [docker-library/docs](https://github.com/docker-library/docs), specifically in [docker-library/docs/sonarqube](https://github.com/docker-library/docs/tree/master/sonarqube).

## What the image provides

- Official SonarQube images for the Community Build and supported commercial editions.
- Versioned tags for repeatable local, test, and production deployments.
- A containerized SonarQube runtime that scanners can send analysis results to.
- Configuration and tag guidance maintained through the Docker Official Images documentation.

The image runs the same SonarQube analysis for developer-written and AI-generated code. Scanners analyze a project and send the results to the running SonarQube instance, where teams can review explainable findings and enforce quality gates.

## The SonarQube product line

- [SonarQube Community Build](https://www.sonarsource.com/products/sonarqube/server/), the open-source server provided by this image.
- [SonarQube Server](https://www.sonarsource.com/products/sonarqube/server/), the self-managed product with additional capabilities.
- [SonarQube Cloud](https://www.sonarsource.com/products/sonarqube/cloud/), the hosted SonarQube service.
- [SonarQube for IDE](https://www.sonarsource.com/products/sonarqube/ide/), real-time analysis while you write or generate code.
- [SonarQube MCP Server](https://github.com/SonarSource/sonarqube-mcp-server), bringing SonarQube analysis into AI agent workflows.
- [SonarQube CLI](https://docs.sonarsource.com/sonarqube-cli), running analysis from the command line.


Have Questions or Feedback?
---------------------------

For support questions ("How do I?", "I got this error, why?", ...), please first read the [documentation](https://docs.sonarqube.org) and then head to the [SonarSource forum](https://community.sonarsource.com/). There are chances that a question similar to yours has already been answered. 

Be aware that this forum is a community, so the standard pleasantries ("Hi", "Thanks", ...) are expected. And if you don't get an answer to your thread, you should sit on your hands for at least three days before bumping it. Operators are not standing by. :-)


Contributing
------------

If you would like to see a new feature or report a bug, please create a new thread in our [forum](https://community.sonarsource.com/tags/c/sq/10/none/docker).

Please be aware that we are not actively looking for feature contributions. We typically accept minor improvements and bug fixes.

With that in mind, if you would like to submit a code contribution, please create a pull request for this repository. Please explain your motives to contribute this change: what problem you are trying to fix, what improvement you are trying to make.

### License

Copyright SonarSource.

SonarQube Community Build is released under the [GNU Lesser General Public License, Version 3.0⁠,](http://www.gnu.org/licenses/lgpl.txt) and packaged with [SSALv1](https://www.sonarsource.com/license/ssal/) analyzers. SonarQube Server Developer, Enterprise, and Data Center Editions are licensed under [SonarQube Server Terms and Conditions](https://www.sonarsource.com/legal/sonarqube/terms-and-conditions/).
