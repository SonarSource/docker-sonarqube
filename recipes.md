# Run SonarQube with a PostgreSQL database

Create this `docker-compose.yml` file

```yaml
sonarqube:
  build: "5.1"
  ports:
   - "9000:9000"
   - "5432:5432"
  environment:
   - SONARQUBE_JDBC_URL=jdbc:postgresql://localhost/sonar

db:
  image: postgres
  net: container:sonarqube
  environment:
   - POSTGRES_USER=sonar
   - POSTGRES_PASSWORD=sonar
```

Use [docker-machine](https://github.com/docker/machine) to start the containers.

```bash
$ docker-compose up
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
