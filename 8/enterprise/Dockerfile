FROM openjdk:11-jre-slim

RUN apt-get update \
    && apt-get install -y curl unzip libfreetype6 libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

# Http port
EXPOSE 9000

RUN groupadd -r sonarqube && useradd -r -g sonarqube sonarqube

ARG SONARQUBE_VERSION=8.1.0.31237
ARG SONARQUBE_ZIP_URL=https://binaries.sonarsource.com/CommercialDistribution/sonarqube-enterprise/sonarqube-enterprise-${SONARQUBE_VERSION}.zip
ENV SONAR_VERSION=${SONARQUBE_VERSION} \
    SONARQUBE_HOME=/opt/sq \
    SONARQUBE_PUBLIC_HOME=/opt/sonarqube

SHELL ["/bin/bash", "-c"]
RUN sed -i -e "s?securerandom.source=file:/dev/random?securerandom.source=file:/dev/urandom?g" \
  "$JAVA_HOME/conf/security/java.security"

RUN set -x \
    && cd /opt \
# download and unzip SQ
    && curl -o sonarqube.zip -fsSL "$SONARQUBE_ZIP_URL" \
    && unzip -q sonarqube.zip \
    && mv "sonarqube-${SONARQUBE_VERSION}" sq \
    && rm sonarqube.zip* \
# empty bin directory from useless scripts
# create copies or delete directories allowed to be mounted as volumes, original directories will be recreated below as symlinks
    && rm --recursive --force "$SONARQUBE_HOME/bin"/* \
    && mv "$SONARQUBE_HOME/conf" "$SONARQUBE_HOME/conf_save" \
    && mv "$SONARQUBE_HOME/extensions" "$SONARQUBE_HOME/extensions_save" \
    && rm --recursive --force "$SONARQUBE_HOME/logs" \
    && rm --recursive --force "$SONARQUBE_HOME/data" \
# create directories to be declared as volumes
# copy into them to ensure they are initialized by 'docker run' when new volume is created
# 'docker run' initialization will not work if volume is bound to the host's filesystem or when volume already exists
# initialization is implemented in 'run.sh' for these cases
    && mkdir --parents "$SONARQUBE_PUBLIC_HOME/conf" \
    && mkdir --parents "$SONARQUBE_PUBLIC_HOME/extensions" \
    && mkdir --parents "$SONARQUBE_PUBLIC_HOME/logs" \
    && mkdir --parents "$SONARQUBE_PUBLIC_HOME/data" \
    && cp --recursive "$SONARQUBE_HOME/conf_save"/* "$SONARQUBE_PUBLIC_HOME/conf/" \
    && cp --recursive "$SONARQUBE_HOME/extensions_save"/* "$SONARQUBE_PUBLIC_HOME/extensions/" \
# create symlinks to volume directories
    && ln -s "$SONARQUBE_PUBLIC_HOME/conf" "$SONARQUBE_HOME/conf" \
    && ln -s "$SONARQUBE_PUBLIC_HOME/extensions" "$SONARQUBE_HOME/extensions" \
    && ln -s "$SONARQUBE_PUBLIC_HOME/logs" "$SONARQUBE_HOME/logs" \
    && ln -s "$SONARQUBE_PUBLIC_HOME/data" "$SONARQUBE_HOME/data" \
    && chown --recursive sonarqube:sonarqube "$SONARQUBE_HOME" "$SONARQUBE_PUBLIC_HOME"

COPY --chown=sonarqube:sonarqube run.sh "$SONARQUBE_HOME/bin/"

USER sonarqube
WORKDIR $SONARQUBE_HOME
ENTRYPOINT ["./bin/run.sh"]
