ARG BASE_VERSION=2026.2.0

FROM eclipse-temurin:25-jdk-noble AS copier
ARG SONARQUBE_VERSION

COPY sonarqube-enterprise-${SONARQUBE_VERSION}.zip /opt/sonarqube.zip

RUN apt-get update && apt-get install -y --no-install-recommends unzip && \
    cd /opt && unzip -q sonarqube.zip


FROM sonarqube:${BASE_VERSION}-enterprise AS base

FROM sonarqube:${BASE_VERSION}-enterprise
ARG SONARQUBE_VERSION
ENV SONAR_VERSION=${SONARQUBE_VERSION}

USER root

RUN rm -rf /opt/sonarqube*

COPY --from=copier /opt/sonarqube-${SONARQUBE_VERSION} /opt/sonarqube
COPY --from=base --chown=root:root --chmod=555 /opt/sonarqube/docker/entrypoint.sh /opt/sonarqube/docker/entrypoint.sh

RUN rm -rf ${SONARQUBE_HOME}/bin/* && \
    ln -s "${SONARQUBE_HOME}/lib/sonar-application-${SONARQUBE_VERSION}.jar" "${SONARQUBE_HOME}/lib/sonarqube.jar" && \
    chown -R sonarqube:root ${SONARQUBE_HOME} && \
    chown -R sonarqube:root "${SQ_DATA_DIR}" "${SQ_EXTENSIONS_DIR}" "${SQ_LOGS_DIR}" "${SQ_TEMP_DIR}" && \
    chmod -R 550 ${SONARQUBE_HOME} && \
    chmod -R 770 "${SQ_DATA_DIR}" "${SQ_EXTENSIONS_DIR}" "${SQ_LOGS_DIR}" "${SQ_TEMP_DIR}"

USER sonarqube
