ARG SONARQUBE_VERSION=8.2.0.32929

FROM adoptopenjdk/openjdk11:alpine-jre as build
ARG SONARQUBE_VERSION
ARG SONARQUBE_ZIP_URL=https://binaries.sonarsource.com/CommercialDistribution/sonarqube-enterprise/sonarqube-enterprise-${SONARQUBE_VERSION}.zip
ENV SONARQUBE_HOME=/opt/sonarqube \
    SQ_DATA_DIR="/opt/sonarqube/data" \
    SQ_EXTENSIONS_DIR="/opt/sonarqube/extensions" \
    SQ_LOGS_DIR="/opt/sonarqube/logs" \
    SQ_TEMP_DIR="/opt/sonarqube/temp"

RUN set -ex \
    && apk update \
    && apk upgrade \
    && apk add --no-cache --update gnupg unzip curl \
    # pub   2048R/D26468DE 2015-05-25
    #       Key fingerprint = F118 2E81 C792 9289 21DB  CAB4 CFCA 4A29 D264 68DE
    # uid                  sonarsource_deployer (Sonarsource Deployer) <infra@sonarsource.com>
    # sub   2048R/06855C1D 2015-05-25
    && for server in $(shuf -e ha.pool.sks-keyservers.net \
                            hkp://p80.pool.sks-keyservers.net:80 \
                            keyserver.ubuntu.com \
                            hkp://keyserver.ubuntu.com:80 \
                            pgp.mit.edu) ; do \
        gpg --batch --keyserver "$server" --recv-keys F1182E81C792928921DBCAB4CFCA4A29D26468DE && break || : ; \
    done \
    && mkdir --parents /opt \
    && cd /opt \
    && curl --fail --location --output sonarqube.zip --silent --show-error  "$SONARQUBE_ZIP_URL" \
    && curl --fail --location --output sonarqube.zip.asc --silent --show-error  "${SONARQUBE_ZIP_URL}.asc" \
    && gpg --batch --verify sonarqube.zip.asc sonarqube.zip \
    && unzip -q sonarqube.zip \
    && mv "sonarqube-${SONARQUBE_VERSION}" sonarqube \
    && rm sonarqube.zip* \
    && rm -rf $SONARQUBE_HOME/bin/* \
    # this 777 will be replaced by 700 at runtime (allows semi-arbitrary "--user" values) 
    && chmod -R 777 "${SQ_DATA_DIR}" "${SQ_EXTENSIONS_DIR}" "${SQ_LOGS_DIR}" "${SQ_TEMP_DIR}"
    
COPY run.sh sonar.sh $SONARQUBE_HOME/bin/

FROM adoptopenjdk/openjdk11:alpine-jre
ARG SONARQUBE_VERSION
ENV SONAR_VERSION="${SONARQUBE_VERSION}" \
    SONARQUBE_HOME="/opt/sonarqube" \
    SQ_DATA_DIR="/opt/sonarqube/data" \
    SQ_EXTENSIONS_DIR="/opt/sonarqube/extensions" \
    SQ_LOGS_DIR="/opt/sonarqube/logs" \
    SQ_TEMP_DIR="/opt/sonarqube/temp" \
    ES_TMPDIR="/opt/sonarqube/temp"

RUN set -ex \
    && addgroup -S -g 1000 sonarqube \
    && adduser -S -D -u 1000 -G sonarqube sonarqube \
    && sed --in-place --expression="s?securerandom.source=file:/dev/random?securerandom.source=file:/dev/urandom?g" "${JAVA_HOME}/conf/security/java.security" \
    && apk update \
    && apk upgrade \
    && apk add --no-cache --update bash su-exec ttf-dejavu

COPY --chown=sonarqube:sonarqube --from=build ${SONARQUBE_HOME} ${SONARQUBE_HOME}

WORKDIR ${SONARQUBE_HOME}
EXPOSE 9000
ENTRYPOINT ["bin/run.sh"]
CMD ["bin/sonar.sh"]