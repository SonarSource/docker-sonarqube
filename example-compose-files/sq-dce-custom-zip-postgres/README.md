# This is used mostly for internal development

You need Docker and docker-compose installed.

> Please note that depending on your Docker install the compose cmd can be either `docker-compose` or `docker compose`.

You need to put your SonarQube zip into this **sq-dce-custom-zip-postgres directory**.

bash
```
cd example-compose-files/sq-dce-custom-zip-postgres
ls -al
11:39 .
11:33 ..
11:33 Dockerfile-app
11:33 Dockerfile-search
11:39 README
11:37 docker-compose.yml
11:33 sonarqube-datacenter-10.8.1.102637.zip
11:33 unrestricted_client_body_size.conf
```

You need to specify the SonarQube version that will be used either with an export like this `export SONARQUBE_VERSION=10.8.1.102637` or by changing the docker-compose file.

You can then run this command to start the SonarQube instance:

```
docker-compose up -d --build
```

When all nodes are healthy with `docker-compose ps`

bash
```
NAME                                     IMAGE                                 SERVICE     CREATED          STATUS                      PORTS
sq-dce-custom-zip-postgres-db-1          postgres:15                           db          10 minutes ago   Up 10 minutes (healthy)     5432/tcp
sq-dce-custom-zip-postgres-proxy-1       jwilder/nginx-proxy                   proxy       10 minutes ago   Up 10 minutes               0.0.0.0:80->80/tcp
sq-dce-custom-zip-postgres-search-1-1    sq-dce-custom-zip-postgres-search-1   search-1    2 minutes ago    Up 2 minutes (healthy)      9000/tcp
sq-dce-custom-zip-postgres-search-2-1    sq-dce-custom-zip-postgres-search-2   search-2    2 minutes ago    Up 2 minutes (healthy)      9000/tcp
sq-dce-custom-zip-postgres-sonarqube-1   sq-dce-custom-zip-postgres-sonarqube  sonarqube   2 minutes ago    Up About a minute (healthy) 9000/tcp
sq-dce-custom-zip-postgres-sonarqube-2   sq-dce-custom-zip-postgres-sonarqube  sonarqube   2 minutes ago    Up About a minute (healthy) 9000/tcp
```

You can access your SonarQube instance trought the reverse proxy to this url `http://sonarqube.dev.local/` this dns entry `127.0.0.1 sonarqube.dev.local` needs to be set on your `/etc/hosts`.

## Debug

If you experience random crash of SonarQube search/app, the top most cause will be memory. Please make sure your Docker desktop has enought resources (we advise at least 18Gb of memory)

## External access

If you want that your SonarQube instance access something on your host (like the telemetry listener) you can use this `host.docker.internal` dns name. This will be routed to the localhost of your **Host machine**