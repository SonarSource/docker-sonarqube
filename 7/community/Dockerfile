ARG SQ_VERSION=7.9.1

FROM openjdk:11-slim AS build
ARG SQ_VERSION
ENV SONAR_VERSION=${SQ_VERSION} \
    SONARQUBE_HOME=/opt/sonarqube
RUN apt-get update \
    && apt-get install -y curl gnupg2 unzip
# pub   2048R/D26468DE 2015-05-25
#       Key fingerprint = F118 2E81 C792 9289 21DB  CAB4 CFCA 4A29 D264 68DE
# uid                  sonarsource_deployer (Sonarsource Deployer) <infra@sonarsource.com>
# sub   2048R/06855C1D 2015-05-25
RUN for server in $(shuf -e ha.pool.sks-keyservers.net \
                            hkp://p80.pool.sks-keyservers.net:80 \
                            keyserver.ubuntu.com \
                            hkp://keyserver.ubuntu.com:80 \
                            pgp.mit.edu) ; do \
        gpg --batch --keyserver "$server" --recv-keys F1182E81C792928921DBCAB4CFCA4A29D26468DE && break || : ; \
    done
RUN set -x \
    && cd /opt \
    && curl -o sonarqube.zip -fSL https://binaries.sonarsource.com/Distribution/sonarqube/sonarqube-$SONAR_VERSION.zip \
    && curl -o sonarqube.zip.asc -fSL https://binaries.sonarsource.com/Distribution/sonarqube/sonarqube-$SONAR_VERSION.zip.asc \
    && gpg --batch --verify sonarqube.zip.asc sonarqube.zip \
    && unzip -q sonarqube.zip \
    && mv sonarqube-$SONAR_VERSION sonarqube \
    && rm sonarqube.zip* \
    && rm -rf $SONARQUBE_HOME/bin/*
COPY run.sh $SONARQUBE_HOME/bin/

FROM openjdk:11-slim
ARG SQ_VERSION
ENV SONAR_VERSION=${SQ_VERSION} \
    SONARQUBE_HOME=/opt/sonarqube \
    SONARQUBE_JDBC_USERNAME=sonar \
    SONARQUBE_JDBC_PASSWORD=sonar \
    SONARQUBE_JDBC_URL=""
RUN groupadd -r sonarqube \
    && useradd -r -g sonarqube sonarqube
COPY --chown=sonarqube:sonarqube --from=build $SONARQUBE_HOME $SONARQUBE_HOME
EXPOSE 9000
VOLUME "$SONARQUBE_HOME/data"
WORKDIR $SONARQUBE_HOME
USER sonarqube
ENTRYPOINT ["./bin/run.sh"]
