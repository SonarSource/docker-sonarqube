docker-sonarqube
================

# Supported tags and respective Dockerfile links

* `5.1.2`, `latest` ([Dockerfile](https://github.com/SonarSource/docker-sonarqube/blob/master/5.1.2/Dockerfile))
* `4.5.4`, `lts` ([Dockerfile](https://github.com/SonarSource/docker-sonarqube/blob/master/4.5.4/Dockerfile))

For more information about this image and its history, please see the
[relevant manifest file](https://github.com/docker-library/official-images/blob/master/library/sonarqube) (`library/sonarqube`) in the `docker-library/official-images` [GitHub repo](https://github.com/docker-library/official-images).

# What is SonarQube?

![SonarQube - Put your technical debt under control](logo.png)

Put your technical debt under control [http://www.sonarqube.org/](http://www.sonarqube.org/)

# How to use this image

## Run SonarQube

The server is started this way:

    docker run -d --name sonarqube -p 9000:9000 -p 9092:9092 sonarqube:5.1

To analyse a project:

    $ On Linux:
    mvn sonar:sonar

    $ With boot2docker:
    mvn sonar:sonar -Dsonar.host.url=http://$(boot2docker ip):9000 -Dsonar.jdbc.url="jdbc:h2:tcp://$(boot2docker ip)/sonar"

## Database configuration

By default the image will use an embedded H2 database that is not suited for production.

The production database is configured with theses variables:
`SONARQUBE_JDBC_USERNAME`, `SONARQUBE_JDBC_PASSWORD` and `SONARQUBE_JDBC_URL`.

    docker run -d --name sonarqube \
    -p 9000:9000 -p 9092:9092 \
    -e SONARQUBE_JDBC_USERNAME=sonar \
    -e SONARQUBE_JDBC_PASSWORD=sonar \
    -e SONARQUBE_JDBC_URL=jdbc:postgresql://localhost/sonar \
    sonarqube:5.1

More recipes can be found [here](https://github.com/SonarSource/docker-sonarqube/blob/master/recipes.md)

## Administration

The administration guide can be found [here](http://docs.sonarqube.org/display/SONAR/Administration+Guide).

# License

This image is distributed under the [license LGPL v3](http://www.gnu.org/licenses/lgpl.txt).

# Supported Docker versions

This image is officially supported on Docker version 1.6.0.

Support for older versions (down to 1.0) is provided on a best-effort basis.

# User Feedback

## Issues

If you have any problems with or questions about this image, please contact us
through a [GitHub issue](https://github.com/SonarSource/docker-sonarqube/issues).

## Contributing

You are invited to contribute new features, fixes, or updates, large or small; we are always thrilled to receive pull requests,
and do our best to process them as fast as we can.

Before you start to code, we recommend discussing your plans through a [GitHub issue](https://github.com/SonarSource/docker-sonarqube/issues),
especially for more ambitious contributions.
This gives other contributors a chance to point you in the right direction,
give you feedback on your design, and help you find out if someone else is working on the same thing.
