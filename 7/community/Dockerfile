FROM openjdk:11-jre-slim

RUN apt-get update \
    && apt-get install -y curl gnupg2 unzip \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get autoclean

ARG PUID=999
ARG PGID=999
ARG SONARQUBE_VERSION=7.9.1
ARG SONARQUBE_ZIP_URL=https://binaries.sonarsource.com/Distribution/sonarqube/sonarqube-${SONARQUBE_VERSION}.zip
ARG SONARQUBE_ZIP_DIR=/tmp/zip
ARG SONARQUBE_ZIP_LOCATION=$SONARQUBE_ZIP_DIR/sonarqube-${SONARQUBE_VERSION}.zip

# Http port
EXPOSE 9000

ENV SONAR_VERSION=${SONARQUBE_VERSION} \
    SONARQUBE_HOME=/opt/sq \
    SONARQUBE_PUBLIC_HOME=/opt/sonarqube \
    SONARQUBE_JDBC_USERNAME=sonar \
    SONARQUBE_JDBC_PASSWORD=sonar \
    SONARQUBE_JDBC_URL="" \
    PUID=$PUID \
    PGID=$PGID

RUN groupadd -g $PGID -r sonarqube && useradd -u $PUID -r -g sonarqube sonarqube -d $SONARQUBE_HOME

COPY zip/* "$SONARQUBE_ZIP_DIR"/

SHELL ["/bin/bash", "-c"]

RUN sed -i -e "s?securerandom.source=file:/dev/random?securerandom.source=file:/dev/urandom?g" \
  "$JAVA_HOME/conf/security/java.security"

RUN set -x \
    && cd /opt \
    &&  if [ -f "$SONARQUBE_ZIP_LOCATION" ] ; \
          then cp "$SONARQUBE_ZIP_LOCATION" sonarqube.zip; \
          rm -Rf "${SONARQUBE_ZIP_DIR}"; \
        else \
          for server in $(shuf -e ha.pool.sks-keyservers.net \
                                      hkp://p80.pool.sks-keyservers.net:80 \
                                      keyserver.ubuntu.com \
                                      hkp://keyserver.ubuntu.com:80 \
                                      pgp.mit.edu); \
                  do \
                  gpg --batch --keyserver "$server" --recv-keys F1182E81C792928921DBCAB4CFCA4A29D26468DE && break || : ; \
                  done && \
          curl -o sonarqube.zip -fSL https://binaries.sonarsource.com/Distribution/sonarqube/sonarqube-$SONAR_VERSION.zip && \
          curl -o sonarqube.zip.asc -fSL https://binaries.sonarsource.com/Distribution/sonarqube/sonarqube-$SONAR_VERSION.zip.asc && \
          curl -o sonarqube.zip -fsSL "${SONARQUBE_ZIP_URL}" ;\
        fi \
    && unzip -q sonarqube.zip \
    && mv "sonarqube-${SONARQUBE_VERSION}" $SONARQUBE_HOME \
    && chown -R sonarqube:sonarqube $SONARQUBE_HOME \
    && rm sonarqube.zip* \
    && rm --recursive --force "$SONARQUBE_HOME/bin"/* \
    && mv "$SONARQUBE_HOME/conf" "$SONARQUBE_HOME/conf_save" \
    && mv "$SONARQUBE_HOME/extensions" "$SONARQUBE_HOME/extensions_save" \
    && rm --recursive --force "$SONARQUBE_HOME/logs" \
    && rm --recursive --force "$SONARQUBE_HOME/data" \
    && mkdir --parents "$SONARQUBE_PUBLIC_HOME/conf" \
    && mkdir --parents "$SONARQUBE_PUBLIC_HOME/extensions" \
    && mkdir --parents "$SONARQUBE_PUBLIC_HOME/logs" \
    && mkdir --parents "$SONARQUBE_PUBLIC_HOME/data" \
    && cp --recursive "$SONARQUBE_HOME/conf_save"/* "$SONARQUBE_PUBLIC_HOME/conf/" \
    && cp --recursive "$SONARQUBE_HOME/extensions_save"/* "$SONARQUBE_PUBLIC_HOME/extensions/" \
    && ln -s "$SONARQUBE_PUBLIC_HOME/conf" "$SONARQUBE_HOME/conf" \
    && ln -s "$SONARQUBE_PUBLIC_HOME/extensions" "$SONARQUBE_HOME/extensions" \
    && ln -s "$SONARQUBE_PUBLIC_HOME/logs" "$SONARQUBE_HOME/logs" \
    && ln -s "$SONARQUBE_PUBLIC_HOME/data" "$SONARQUBE_HOME/data" \
    && chown --recursive sonarqube:sonarqube "$SONARQUBE_HOME" "$SONARQUBE_PUBLIC_HOME"

    COPY --chown=sonarqube:sonarqube run.sh "$SONARQUBE_HOME/bin/"

    USER sonarqube
    WORKDIR $SONARQUBE_HOME
    ENTRYPOINT ["./bin/run.sh"]
