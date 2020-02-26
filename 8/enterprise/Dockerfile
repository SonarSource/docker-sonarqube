FROM openjdk:11-jre-slim

RUN apt-get update \
    && apt-get install -y curl unzip gnupg2 libfreetype6 libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

# Http port
EXPOSE 9000

RUN groupadd -r sonarqube && useradd -r -g sonarqube sonarqube

ARG SONARQUBE_VERSION=8.2.0.32929
ARG SONARQUBE_ZIP_URL=https://binaries.sonarsource.com/CommercialDistribution/sonarqube-enterprise/sonarqube-enterprise-${SONARQUBE_VERSION}.zip
ENV SONAR_VERSION=${SONARQUBE_VERSION} \
    SONARQUBE_HOME=/opt/sonarqube

SHELL ["/bin/bash", "-c"]
RUN sed -i -e "s?securerandom.source=file:/dev/random?securerandom.source=file:/dev/urandom?g" \
  "$JAVA_HOME/conf/security/java.security"

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
    && curl -o sonarqube.zip -fsSL "${SONARQUBE_ZIP_URL}" \
    && curl -o sonarqube.zip.asc -fSL "${SONARQUBE_ZIP_URL}.asc" \
    && gpg --batch --verify sonarqube.zip.asc sonarqube.zip \
    && unzip -q sonarqube.zip \
    && mv "sonarqube-${SONARQUBE_VERSION}" sonarqube \
    && rm sonarqube.zip* \
    && chown --recursive sonarqube:sonarqube "$SONARQUBE_HOME"

COPY --chown=sonarqube:sonarqube run.sh "$SONARQUBE_HOME/bin/"

USER sonarqube
WORKDIR $SONARQUBE_HOME
ENTRYPOINT ["./bin/run.sh"]
