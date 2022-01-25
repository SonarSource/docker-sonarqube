# Examples

This section provides examples on how to run SonarQube server in a container:
- using [docker commands](#run-sonarqube-using-docker-commands)
- using [docker-compose](#run-sonarqube-using-docker-compose)

To analyze a project check our [scanner docs](https://docs.sonarqube.org/latest/analysis/overview/).

## Run SonarQube using docker commands
Before you start SonarQube, we recommend creating volumes to store SonarQube data, logs, temporary data and extensions. If you don't do that, you can loose them when you decide to update to newer version of SonarQube or upgrade to a higher SonarQube edition. Commands to create the volumes: 
```bash
$> docker volume create --name sonarqube_data
$> docker volume create --name sonarqube_extensions
$> docker volume create --name sonarqube_logs
$> docker volume create --name sonarqube_temp
``` 

After that you can start the SonarQube server (this example uses the Community Edition):
```bash
$> docker run \
    -v sonarqube_data:/opt/sonarqube/data \
    -v sonarqube_extensions:/opt/sonarqube/extensions \
    -v sonarqube_logs:/opt/sonarqube/logs \
    --name="sonarqube" -p 9000:9000 sonarqube:community
```
The above command starts SonarQube with an embedded database. We recommend starting the instance with a separate database
by providing `SONAR_JDBC_URL`, `SONAR_JDBC_USERNAME` and `SONAR_JDBC_PASSWORD` like this:
```bash
$> docker run \
    -v sonarqube_data:/opt/sonarqube/data \
    -v sonarqube_extensions:/opt/sonarqube/extensions \
    -v sonarqube_logs:/opt/sonarqube/logs \
    -e SONAR_JDBC_URL="..." \
    -e SONAR_JDBC_USERNAME="..." \
    -e SONAR_JDBC_PASSWORD="..." \
    --name="sonarqube" -p 9000:9000 sonarqube:community
```

## Run SonarQube using Docker Compose
### Requirements

 * Docker Engine 20.10+
 * Docker Compose 2.0.0+

### SonarQube with Postgres:

Go to [this directory](example-compose-files/sq-with-h2) to run SonarQube in development mode or [this directory](example-compose-files/sq-with-postgres) to run both SonarQube and PostgreSQL. Then run [docker-compose](https://github.com/docker/compose):

```bash
$ docker-compose up
```

To restart SonarQube container (for example after upgrading or installing a plugin):

```bash
$ docker-compose restart sonarqube
```
