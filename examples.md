# SonarQube examples

## Requirements

 * Docker Engine 1.10.1+
 * Docker Compose 1.6.0+

## Run SonarQube with Postgres

Go to [this directory](example-compose-files/sq-with-postgres) and run both SonarQube and PostgreSQL containers using [docker-compose](https://github.com/docker/compose):

```bash
$ docker-compose up
```

Restart SonarQube container (for example after upgrading or installing a plugin):

```bash
$ docker-compose restart sonarqube
```

Analyze a project:

[See scanner docs](https://docs.sonarqube.org/latest/analysis/overview/)
