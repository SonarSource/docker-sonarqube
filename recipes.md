# Run SonarQube with a PostgreSQL database

## Requirements

 * Docker Engine 1.9
 * Docker Compose 1.6

## Compose file

Create `docker-compose.yml` file from [this example](recipes/docker-compose-postgres-example.yml).

Use [docker-compose](https://github.com/docker/compose) to start the containers.

```bash
$ docker-compose up
```

Restart the containers (after plugin upgrade or install for example).

```bash
$ docker-compose restart sonarqube
```

Analyse a project:

```bash
mvn sonar:sonar \
  -Dsonar.host.url=http://$(boot2docker ip):9000
```

## To be improved

 + Backup
 + Clustering
 + Upgrade
 + Admin password
 + Plugins
 + ...
