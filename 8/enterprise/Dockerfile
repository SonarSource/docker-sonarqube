FROM openjdk:11-jre-slim

ARG SONARQUBE_VERSION=8.0
ARG SONARQUBE_ZIP_SERVER=binaries.sonarsource.com
ARG SONARQUBE_ZIP_URL=https://${SONARQUBE_ZIP_SERVER}/CommercialDistribution/sonarqube-enterprise/sonarqube-enterprise-${SONARQUBE_VERSION}.zip
ARG SONARQUBE_ZIP_USERNAME
ARG SONARQUBE_ZIP_PASSWORD
ENV SONAR_VERSION=${SONARQUBE_VERSION} \
    SONARQUBE_HOME=/opt/sq \
    SONARQUBE_PUBLIC_HOME=/opt/sonarqube \
    SONARQUBE_JDBC_USERNAME=sonar \
    SONARQUBE_JDBC_PASSWORD=sonar \
    SONARQUBE_JDBC_URL=""

RUN apt-get update \
    && apt-get install -y curl unzip \
    && rm -rf /var/lib/apt/lists/*

# Http port
EXPOSE 9000

RUN groupadd -r sonarqube && useradd -r -g sonarqube sonarqube

SHELL ["/bin/bash", "-c"]
# download and unzip SQ
RUN set -x \
    && cd /opt \
    && if [ "x$SONARQUBE_ZIP_USERNAME" = "x" ] ; \
        then curl -o sonarqube.zip -fsSL "$SONARQUBE_ZIP_URL" ; \
        else curl -o sonarqube.zip -fsSL --netrc-file <(cat <<<"machine $SONARQUBE_ZIP_SERVER login $SONARQUBE_ZIP_USERNAME password $SONARQUBE_ZIP_PASSWORD") "$SONARQUBE_ZIP_URL" ; \
        fi \
    && unzip -q sonarqube.zip \
    && mv "sonarqube-${SONARQUBE_VERSION}" sq \
    && rm sonarqube.zip*

# empty bin directory from useless scripts
# create copies or delete directories allowed to be mounted as volumes, original directories will be recreated below as symlinks
RUN rm --recursive --force "$SONARQUBE_HOME/bin"/* \
    && mv "$SONARQUBE_HOME/conf" "$SONARQUBE_HOME/conf_save" \
    && mv "$SONARQUBE_HOME/extensions" "$SONARQUBE_HOME/extensions_save" \
    && rm --recursive --force "$SONARQUBE_HOME/logs" \
    && rm --recursive --force "$SONARQUBE_HOME/data"

# create directories to be declared as volumes
# copy into them to ensure they are initialized by 'docker run' when new volume is created
# 'docker run' initialization will not work if volume is bound to the host's filesystem or when volume already exists
# initialization is implemented in 'run.sh' for these cases
RUN mkdir --parents "$SONARQUBE_PUBLIC_HOME/conf" \
    && mkdir --parents "$SONARQUBE_PUBLIC_HOME/extensions" \
    && mkdir --parents "$SONARQUBE_PUBLIC_HOME/logs" \
    && mkdir --parents "$SONARQUBE_PUBLIC_HOME/data" \
    && cp --recursive "$SONARQUBE_HOME/conf_save"/* "$SONARQUBE_PUBLIC_HOME/conf/" \
    && cp --recursive "$SONARQUBE_HOME/extensions_save"/* "$SONARQUBE_PUBLIC_HOME/extensions/"

RUN chown --recursive sonarqube:sonarqube "$SONARQUBE_HOME" "$SONARQUBE_PUBLIC_HOME"

USER sonarqube
# create symlinks to volume directories
RUN ln -s "$SONARQUBE_PUBLIC_HOME/conf" "$SONARQUBE_HOME/conf" \
    && ln -s "$SONARQUBE_PUBLIC_HOME/extensions" "$SONARQUBE_HOME/extensions" \
    && ln -s "$SONARQUBE_PUBLIC_HOME/logs" "$SONARQUBE_HOME/logs" \
    && ln -s "$SONARQUBE_PUBLIC_HOME/data" "$SONARQUBE_HOME/data"

COPY --chown=sonarqube:sonarqube run.sh "$SONARQUBE_HOME/bin/"

WORKDIR $SONARQUBE_HOME
ENTRYPOINT ["./bin/run.sh"]
