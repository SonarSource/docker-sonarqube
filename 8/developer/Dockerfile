FROM openjdk:11-jre-slim

ARG SONARQUBE_VERSION=8.0
ARG SONARQUBE_ZIP_URL=https://binaries.sonarsource.com/CommercialDistribution/sonarqube-developer/sonarqube-developer-${SONARQUBE_VERSION}.zip
ARG SONARQUBE_ASC_URL=${SONARQUBE_ZIP_URL}.zip.asc
ARG SONARQUBE_ZIP_DIR=/tmp/zip
ARG SONARQUBE_ZIP_LOCATION=$SONARQUBE_ZIP_DIR/sonarqube-${SONARQUBE_VERSION}.zip
ARG SONARQUBE_KEY=F1182E81C792928921DBCAB4CFCA4A29D26468DE

ENV SONAR_VERSION=${SONARQUBE_VERSION} \
    SONARQUBE_HOME=/opt/sq \
    SONARQUBE_USER=sonarqube \
    SONARQUBE_PUBLIC_HOME=/opt/sonarqube \
    SONARQUBE_KEY=${SONARQUBE_KEY}

COPY zip/* "${SONARQUBE_ZIP_DIR}"/

WORKDIR /opt

SHELL ["/bin/bash", "-c"]

RUN apt-get update \
    && apt-get -y upgrade \
    && apt-get install -y curl gnupg2 libfontconfig1 libfreetype6 unzip --no-install-recommends \
    && groupadd -r "${SONARQUBE_USER}" \
    && useradd -r -g "${SONARQUBE_USER}" "${SONARQUBE_USER}" \
    && sed -i -e "s?securerandom.source=file:/dev/random?securerandom.source=file:/dev/urandom?g" \
  "${JAVA_HOME}/conf/security/java.security" \
    && set -x \
# download and unzip SQ
    && if [ -f "${SONARQUBE_ZIP_LOCATION}" ] ; \
        then cp "${SONARQUBE_ZIP_LOCATION}" sonarqube.zip; \
        else curl -o sonarqube.zip -fsSL "${SONARQUBE_ZIP_URL}" ; \
        fi \
    && curl -o sonarqube.zip.asc "${SONARQUBE_ASC_URL}" \
    && curl -o "${SONAR_SOURCE_KEY}.key" -fsSL "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x${SONARQUBE_KEY}" \
    && gpg --import "${SONAR_SOURCE_KEY}.key" \
    && gpg --no-default-keyring --verify sonarqube.zip.asc || exit 1 \
    && rm -Rf "${SONARQUBE_ZIP_DIR}" \
    && unzip -q sonarqube.zip \
    && mv "sonarqube-${SONARQUBE_VERSION}" sq \
    && rm sonarqube.zip* \
# empty bin directory from useless scripts
# create copies or delete directories allowed to be mounted as volumes, original directories will be recreated below as symlinks
    && rm --recursive --force "${SONARQUBE_HOME}/bin"/* \
    && mv "${SONARQUBE_HOME}/conf" "${SONARQUBE_HOME}/conf_save" \
    && mv "${SONARQUBE_HOME}/extensions" "${SONARQUBE_HOME}/extensions_save" \
    && rm --recursive --force "${SONARQUBE_HOME}/logs" \
    && rm --recursive --force "${SONARQUBE_HOME}/data" \
# create directories to be declared as volumes
# copy into them to ensure they are initialized by 'docker run' when new volume is created
# 'docker run' initialization will not work if volume is bound to the host's filesystem or when volume already exists
# initialization is implemented in 'run.sh' for these cases
    && mkdir --parents "${SONARQUBE_PUBLIC_HOME}/conf" \
    && mkdir --parents "${SONARQUBE_PUBLIC_HOME}/extensions" \
    && mkdir --parents "${SONARQUBE_PUBLIC_HOME}/logs" \
    && mkdir --parents "${SONARQUBE_PUBLIC_HOME}/data" \
    && cp --recursive "${SONARQUBE_HOME}/conf_save"/* "${SONARQUBE_PUBLIC_HOME}/conf/" \
    && cp --recursive "${SONARQUBE_HOME}/extensions_save"/* "${SONARQUBE_PUBLIC_HOME}/extensions/" \
# create symlinks to volume directories
    && ln -s "${SONARQUBE_PUBLIC_HOME}/conf" "${SONARQUBE_HOME}/conf" \
    && ln -s "${SONARQUBE_PUBLIC_HOME}/extensions" "${SONARQUBE_HOME}/extensions" \
    && ln -s "${SONARQUBE_PUBLIC_HOME}/logs" "${SONARQUBE_HOME}/logs" \
    && ln -s "${SONARQUBE_PUBLIC_HOME}/data" "${SONARQUBE_HOME}/data" \
    && chown --recursive "${SONARQUBE_USER}:${SONARQUBE_USER}" "${SONARQUBE_HOME}" "${SONARQUBE_PUBLIC_HOME}" \
    && apt-get -y purge curl gnupg2 unzip \
    && apt-get -y autoremove \
    && rm -rf /var/lib/apt/lists/*

COPY --chown="${SONARQUBE_USER}:${SONARQUBE_USER}" run.sh "${SONARQUBE_HOME}/bin/"

# Http port
EXPOSE 9000

USER "${SONARQUBE_USER}"
WORKDIR "${SONARQUBE_HOME}"
ENTRYPOINT ["./bin/run.sh"]
