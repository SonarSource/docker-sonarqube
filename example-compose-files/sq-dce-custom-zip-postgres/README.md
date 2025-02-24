# Example of SonarQube DCE running on an IPv6 environment.

You need Docker and docker-compose installed.

> Please note that depending on your Docker install the compose cmd can be either `docker-compose` or `docker compose`.

You need to put your SonarQube Server zip into this **sq-dce-custom-zip-postgres directory**.

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
11:33 sonarqube-datacenter-2025.1.0.102418.zip
11:33 unrestricted_client_body_size.conf
```

You need to specify the SonarQube Server version that will be used either with an export like this `export SONARQUBE_VERSION=2025.1.0.102418` or by changing the docker-compose file.

You can then run this command to start the SonarQube Server instance:

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

You can access your SonarQube Server instance through the reverse proxy with this url `http://sonarqube.dev.local/`. (the DNS entry `127.0.0.1 sonarqube.dev.local` needs to be set on your `/etc/hosts`).

## Troubleshooting

If you experience random crash of SonarQube Server search/app, it will be likely due to memory shortage. Please make sure your Docker desktop has enough resources (we advise at least 18Gb of memory).

## External access

If you want that your SonarQube Server instance access something on your host (like the telemetry listener) you can use the `host.docker.internal` dns name. This will be routed to the localhost of your **Host machine**.