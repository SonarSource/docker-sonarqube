# Run SonarQube with a PostgreSQL database

Create this `docker-compose.yml` file

```yaml
sonarqube:
  build: "5.2"
  ports:
   - "9000:9000"
  links:
   - db
  environment:
   - SONARQUBE_JDBC_URL=jdbc:postgresql://db:5432/sonar
  volumes_from:
   - plugins

db:
  image: postgres
  volumes_from:
    - datadb
  environment:
   - POSTGRES_USER=sonar
   - POSTGRES_PASSWORD=sonar

datadb:
  image: postgres:9.4
  volumes:
    - /var/lib/postgresql
  command: /bin/true

plugins:
  build: "5.2"
  volumes:
   - /opt/sonarqube/extensions
   - /opt/sonarqube/lib/bundled-plugins
  command: /bin/true
```

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
  -Dsonar.host.url=http://$(boot2docker ip):9000 \
  -Dsonar.jdbc.url=jdbc:postgresql://$(boot2docker ip)/sonar
```

## To be improved

 + Backup
 + Clustering
 + Upgrade
 + Admin password
 + Plugins
 + ...
