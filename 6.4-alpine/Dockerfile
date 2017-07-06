FROM openjdk:8-alpine

ENV SONAR_VERSION=6.4
ENV SONARQUBE_HOME=/opt/sonarqube
# Database configuration
# Defaults to using H2
ENV SONARQUBE_JDBC_USERNAME=sonar
ENV SONARQUBE_JDBC_PASSWORD=sonar
ENV SONARQUBE_JDBC_URL=

COPY run.sh $SONARQUBE_HOME/bin/

RUN set -x \
    && apk add --no-cache gnupg unzip \
    && apk add --no-cache libressl wget \

    # pub   2048R/D26468DE 2015-05-25
    #       Key fingerprint = F118 2E81 C792 9289 21DB  CAB4 CFCA 4A29 D264 68DE
    # uid                  sonarsource_deployer (Sonarsource Deployer) <infra@sonarsource.com>
    # sub   2048R/06855C1D 2015-05-25
    && gpg --keyserver ha.pool.sks-keyservers.net --recv-keys F1182E81C792928921DBCAB4CFCA4A29D26468DE \

    && mkdir /opt \
    && cd /opt \
    && wget -O sonarqube.zip --no-verbose https://sonarsource.bintray.com/Distribution/sonarqube/sonarqube-$SONAR_VERSION.zip \
    && wget -O sonarqube.zip.asc --no-verbose https://sonarsource.bintray.com/Distribution/sonarqube/sonarqube-$SONAR_VERSION.zip.asc \
    && gpg --batch --verify sonarqube.zip.asc sonarqube.zip \
    && unzip sonarqube.zip \
    && mv sonarqube-$SONAR_VERSION sonarqube \
    && rm sonarqube.zip* \
    && rm -rf $SONARQUBE_HOME/bin/*

VOLUME "$SONARQUBE_HOME/data"

# Http port
EXPOSE 9000

WORKDIR $SONARQUBE_HOME

ENTRYPOINT ["./bin/run.sh"]
