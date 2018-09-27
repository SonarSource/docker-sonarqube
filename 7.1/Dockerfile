FROM openjdk:8

ENV SONAR_VERSION=7.1 \
    SONARQUBE_HOME=/opt/sonarqube \
    # Database configuration
    # Defaults to using H2
    SONARQUBE_JDBC_USERNAME=sonar \
    SONARQUBE_JDBC_PASSWORD=sonar \
    SONARQUBE_JDBC_URL=

# Http port
EXPOSE 9000

RUN groupadd -r sonarqube && useradd -r -g sonarqube sonarqube

# grab gosu for easy step-down from root
RUN set -x \
    && wget -O /usr/local/bin/gosu "https://github.com/tianon/gosu/releases/download/1.10/gosu-$(dpkg --print-architecture)" \
    && wget -O /usr/local/bin/gosu.asc "https://github.com/tianon/gosu/releases/download/1.10/gosu-$(dpkg --print-architecture).asc" \
    && export GNUPGHOME="$(mktemp -d)" \
    && gpg --keyserver ha.pool.sks-keyservers.net --recv-keys B42F6819007F00F88E364FD4036A9C25BF357DD4 \
    && gpg --batch --verify /usr/local/bin/gosu.asc /usr/local/bin/gosu \
    && rm -rf "$GNUPGHOME" /usr/local/bin/gosu.asc \
    && chmod +x /usr/local/bin/gosu \
    && gosu nobody true

RUN set -x \

    # pub   2048R/D26468DE 2015-05-25
    #       Key fingerprint = F118 2E81 C792 9289 21DB  CAB4 CFCA 4A29 D264 68DE
    # uid                  sonarsource_deployer (Sonarsource Deployer) <infra@sonarsource.com>
    # sub   2048R/06855C1D 2015-05-25
    && gpg --keyserver ha.pool.sks-keyservers.net --recv-keys F1182E81C792928921DBCAB4CFCA4A29D26468DE \

    && cd /opt \
    && curl -o sonarqube.zip -fSL https://sonarsource.bintray.com/Distribution/sonarqube/sonarqube-$SONAR_VERSION.zip \
    && curl -o sonarqube.zip.asc -fSL https://sonarsource.bintray.com/Distribution/sonarqube/sonarqube-$SONAR_VERSION.zip.asc \
    && gpg --batch --verify sonarqube.zip.asc sonarqube.zip \
    && unzip sonarqube.zip \
    && mv sonarqube-$SONAR_VERSION sonarqube \
    && chown -R sonarqube:sonarqube sonarqube \
    && rm sonarqube.zip* \
    && rm -rf $SONARQUBE_HOME/bin/*

VOLUME "$SONARQUBE_HOME/data"

# Plangrid Specific Options
COPY run-server /bin/
RUN mkdir -p /opt/plangrid/settings/bin
COPY pgs /opt/plangrid/settings/bin/
ENV PGS_APP="sonarqube"

# Download and vendor in the plugins
RUN mkdir -p $SONARQUBE_HOME/extensions/plugins \
    && cd $SONARQUBE_HOME/extensions/plugins \
    # Free standard
    && wget "https://sonarsource.bintray.com/Distribution/sonar-python-plugin/sonar-python-plugin-1.8.0.1496.jar" \
    && wget "https://sonarsource.bintray.com/Distribution/sonar-scm-git-plugin/sonar-scm-git-plugin-1.2.jar" \
    && wget "https://sonarsource.bintray.com/Distribution/sonar-csharp-plugin/sonar-csharp-plugin-6.5.0.3766.jar" \
    && wget "https://sonarsource.bintray.com/Distribution/sonar-java-plugin/sonar-java-plugin-4.15.0.12310.jar" \
    && wget "https://sonarsource.bintray.com/Distribution/sonar-javascript-plugin/sonar-javascript-plugin-3.2.0.5506.jar" \
    && wget "https://sonarsource.bintray.com/Distribution/sonar-web-plugin/sonar-web-plugin-2.5.0.476.jar" \
    && wget "https://sonarsource.bintray.com/Distribution/sonar-xml-plugin/sonar-xml-plugin-1.4.3.1027.jar" \
    # Commercial (free but need to accept terms&conditions?)
    && wget "https://sonarsource.bintray.com/CommercialDistribution/sonar-cfamily-plugin/sonar-cfamily-plugin-4.14.0.9331.jar" \
    && wget "https://sonarsource.bintray.com/CommercialDistribution/sonar-plsql-plugin/sonar-plsql-plugin-3.0.1.1427.jar" \
    && wget "https://sonarsource.bintray.com/CommercialDistribution/sonar-swift-plugin/sonar-swift-plugin-3.0.0.1969.jar" \
    # Other Plugins
    && wget "https://github.com/uartois/sonar-golang/releases/download/v1.2.11-rc3/sonar-golang-plugin-1.2.11-rc3.jar" \
    && wget "https://github.com/kogitant/sonar-slack-notifier-plugin/releases/download/2.1.2/cks-slack-notifier-2.1.2.jar"

# End Plangrid Specific Options

WORKDIR $SONARQUBE_HOME
COPY run.sh $SONARQUBE_HOME/bin/
ENTRYPOINT ["./bin/run.sh"]
