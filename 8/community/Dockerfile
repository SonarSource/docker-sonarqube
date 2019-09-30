FROM openjdk:11-jre-slim

ARG SONARQUBE_VERSION=8.0
ARG SONARQUBE_ZIP_SERVER=binaries.sonarsource.com
ARG SONARQUBE_ZIP_URL=https://${SONARQUBE_ZIP_SERVER}/Distribution/sonarqube/sonarqube-${SONARQUBE_VERSION}.zip
ARG SONARQUBE_ZIP_USERNAME
ARG SONARQUBE_ZIP_PASSWORD
ENV SONAR_VERSION=${SONARQUBE_VERSION} \
    SONARQUBE_HOME=/opt/sonarqube

RUN apt-get update \
    && apt-get install -y curl unzip \
    && rm -rf /var/lib/apt/lists/*

# Http port
EXPOSE 9000

RUN groupadd -r sonarqube && useradd -r -g sonarqube sonarqube

SHELL ["/bin/bash", "-c"]
RUN set -x \
    && cd /opt \
    && if [ "x$SONARQUBE_ZIP_USERNAME" = "x" ] ; \
        then curl -o sonarqube.zip -fsSL $SONARQUBE_ZIP_URL ; \
        else curl -o sonarqube.zip -fsSL --netrc-file <(cat <<<"machine $SONARQUBE_ZIP_SERVER login $SONARQUBE_ZIP_USERNAME password $SONARQUBE_ZIP_PASSWORD") "$SONARQUBE_ZIP_URL" ; \
        fi \
    && unzip -q sonarqube.zip \
    && mv sonarqube-${SONARQUBE_VERSION} sonarqube \
    && chown -R sonarqube:sonarqube sonarqube \
    && rm sonarqube.zip* \
    && rm -rf $SONARQUBE_HOME/bin/*

VOLUME "$SONARQUBE_HOME/data"

WORKDIR $SONARQUBE_HOME
COPY run.sh $SONARQUBE_HOME/bin/
USER sonarqube
ENTRYPOINT ["./bin/run.sh"]
