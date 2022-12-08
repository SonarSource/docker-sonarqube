FROM eclipse-temurin:11-jdk as build

ENV LANG='en_US.UTF-8' \
    LANGUAGE='en_US:en' \
    LC_ALL='en_US.UTF-8'

#
# SonarQube setup
#
ARG SONARQUBE_VERSION=9.7.1.62043
ARG SONARQUBE_ZIP_URL=https://binaries.sonarsource.com/Distribution/sonarqube/sonarqube-${SONARQUBE_VERSION}.zip
ENV JAVA_HOME='/usr/local/openjdk-11' \
    SONARQUBE_HOME=/opt/sonarqube \
    SONAR_VERSION="${SONARQUBE_VERSION}" \
    SQ_DATA_DIR="/opt/sonarqube/data" \
    SQ_EXTENSIONS_DIR="/opt/sonarqube/extensions" \
    SQ_LOGS_DIR="/opt/sonarqube/logs" \
    SQ_TEMP_DIR="/opt/sonarqube/temp"

RUN set -eux; \
    addgroup --gid 1000 sonarqube; \
    adduser --uid 1000 sonarqube --gid 1000; \
    apt-get update; \
    apt-get install -y gnupg unzip curl bash fonts-dejavu; \
    # pub   2048R/D26468DE 2015-05-25
    #       Key fingerprint = F118 2E81 C792 9289 21DB  CAB4 CFCA 4A29 D264 68DE
    # uid                  sonarsource_deployer (Sonarsource Deployer) <infra@sonarsource.com>
    # sub   2048R/06855C1D 2015-05-25
    for server in $(shuf -e hkps://keys.openpgp.org \
                            hkps://keyserver.ubuntu.com) ; do \
        gpg --batch --keyserver "${server}" --recv-keys 679F1EE92B19609DE816FDE81DB198F93525EC1A && break || : ; \
    done; \
    mkdir --parents /opt; \
    cd /opt; \
    curl --fail --location --output sonarqube.zip --silent --show-error "${SONARQUBE_ZIP_URL}"; \
    curl --fail --location --output sonarqube.zip.asc --silent --show-error "${SONARQUBE_ZIP_URL}.asc"; \
    gpg --batch --verify sonarqube.zip.asc sonarqube.zip; \
    unzip -q sonarqube.zip; \
    mv "sonarqube-${SONARQUBE_VERSION}" sonarqube; \
    rm sonarqube.zip*; \
    rm -rf ${SONARQUBE_HOME}/bin/*; \
    chown -R sonarqube:sonarqube ${SONARQUBE_HOME}; \
    # this 777 will be replaced by 700 at runtime (allows semi-arbitrary "--user" values)
    chmod -R 777 ${SONARQUBE_HOME}; \
    apt-get remove -y gnupg unzip curl;

COPY jre.info jre.info

RUN jlink --verbose \
  --compress 2 \
  --no-header-files \
  --no-man-pages \
  --output jre \
  --add-modules $(cat jre.info) \
  --include-locales en,th

WORKDIR ${SONARQUBE_HOME}
EXPOSE 9000

STOPSIGNAL SIGINT

ENTRYPOINT ["/opt/sonarqube/bin/run.sh"]
CMD ["/opt/sonarqube/bin/sonar.sh"]

FROM ubuntu

ARG SONARQUBE_VERSION=9.7.1.62043
ENV SONARQUBE_HOME=/opt/sonarqube 
ENV JAVA_HOME=/usr/local/openjdk-11

COPY --from=build ${SONARQUBE_HOME} ${SONARQUBE_HOME}
COPY --from=build jre /usr/local/openjdk-11

USER 1000
WORKDIR ${SONARQUBE_HOME}
ENTRYPOINT ["/usr/local/openjdk-11/bin/java","-jar"]
CMD ["lib/sonar-application-9.7.1.62043.jar","-Dsonar.log.console=true"]
