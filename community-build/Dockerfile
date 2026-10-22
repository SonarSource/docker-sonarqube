FROM eclipse-temurin:25-jdk-noble

LABEL io.k8s.description="SonarQube Community Build is a self-managed, automatic code review tool that systematically helps you deliver Clean Code."
LABEL io.openshift.min-cpu=400m
LABEL io.openshift.min-memory=2048M
LABEL io.openshift.non-scalable=true
LABEL io.openshift.tags=sonarqube,static-code-analysis,code-quality,clean-code
LABEL org.opencontainers.image.url=https://github.com/SonarSource/docker-sonarqube

ENV LANG='en_US.UTF-8' \
    LANGUAGE='en_US:en' \
    LC_ALL='en_US.UTF-8'

#
# SonarQube setup
#
ARG SONARQUBE_VERSION=26.9.0.129388
ARG SONARQUBE_ZIP_URL=https://binaries.sonarsource.com/Distribution/sonarqube/sonarqube-${SONARQUBE_VERSION}.zip
ENV DOCKER_RUNNING="true" \
    JAVA_HOME='/opt/java/openjdk' \
    SONARQUBE_HOME=/opt/sonarqube \
    SONAR_VERSION="${SONARQUBE_VERSION}" \
    SQ_DATA_DIR="/opt/sonarqube/data" \
    SQ_EXTENSIONS_DIR="/opt/sonarqube/extensions" \
    SQ_LOGS_DIR="/opt/sonarqube/logs" \
    SQ_TEMP_DIR="/opt/sonarqube/temp"

# Separate stage to use variable expansion
ENV ES_TMPDIR="${SQ_TEMP_DIR}"

RUN set -eux; \
    deluser ubuntu; \
    useradd --system --uid 1000 --gid 0 sonarqube; \
    apt-get update; \
    apt-get --no-install-recommends -y install \
        bash \
        ca-certificates \
        curl \
        fonts-dejavu \
        gnupg \
        unzip; \
    echo "networkaddress.cache.ttl=5" >> "${JAVA_HOME}/conf/security/java.security"; \
    sed --in-place --expression="s?securerandom.source=file:/dev/random?securerandom.source=file:/dev/urandom?g" "${JAVA_HOME}/conf/security/java.security"; \
    # Remove emSign ECC Root CA - G3 from the JDK trust store, matching its removal from the Mozilla root store.
    # The deletion is a no-op once the base image ships without it;
    # the checks fail the build if either trust store still has it.
    emsign_g3_alias='cn_emsign_ecc_root_ca__g3,o_emudhra_technologies_limited,ou_emsign_pki,c_in [jdk]'; \
    emsign_g3_sha256='86:A1:EC:BA:08:9C:4A:8D:3B:BE:27:34:C6:12:BA:34:1D:81:3E:04:3C:F9:E8:A8:62:CD:5C:57:A3:6B:BE:6B'; \
    if keytool -list -cacerts -storepass changeit -alias "${emsign_g3_alias}" > /dev/null 2>&1; then \
        keytool -delete -cacerts -storepass changeit -alias "${emsign_g3_alias}"; \
    fi; \
    keytool -list -cacerts -storepass changeit > /tmp/cacerts.txt; \
    if grep -q "${emsign_g3_sha256}" /tmp/cacerts.txt; then \
        echo "emSign ECC Root CA - G3 is still trusted by the JDK" >&2; exit 1; \
    fi; \
    rm /tmp/cacerts.txt; \
    if [ -e /etc/ssl/certs/emSign_ECC_Root_CA_-_G3.pem ]; then \
        echo "emSign ECC Root CA - G3 is still trusted by the OS" \
            "(ca-certificates $(dpkg-query -W -f='${Version}' ca-certificates))" >&2; \
        exit 1; \
    fi; \
    # pub   2048R/D26468DE 2015-05-25
    #       Key fingerprint = F118 2E81 C792 9289 21DB  CAB4 CFCA 4A29 D264 68DE
    # uid                  sonarsource_deployer (Sonarsource Deployer) <infra@sonarsource.com>
    # sub   2048R/06855C1D 2015-05-25
    for server in $(shuf -e hkps://keyserver.ubuntu.com) ; do \
        gpg --batch --keyserver "${server}" --recv-keys 679F1EE92B19609DE816FDE81DB198F93525EC1A && break || : ; \
    done; \
    cd /opt; \
    curl --proto "=https" --fail --output sonarqube.zip --silent --show-error "${SONARQUBE_ZIP_URL}"; \
    curl --proto "=https" --fail --output sonarqube.zip.asc --silent --show-error "${SONARQUBE_ZIP_URL}.asc"; \
    gpg --batch --verify sonarqube.zip.asc sonarqube.zip; \
    unzip -q sonarqube.zip; \
    mv "sonarqube-${SONARQUBE_VERSION}" sonarqube; \
    rm sonarqube.zip*; \
    rm -rf ${SONARQUBE_HOME}/bin/*; \
    ln -s "${SONARQUBE_HOME}/lib/sonar-application-${SONARQUBE_VERSION}.jar" "${SONARQUBE_HOME}/lib/sonarqube.jar"; \
    chown -R sonarqube:root ${SONARQUBE_HOME}; \
    chown -R sonarqube:root "${SQ_DATA_DIR}" "${SQ_EXTENSIONS_DIR}" "${SQ_LOGS_DIR}" "${SQ_TEMP_DIR}"; \
    chmod -R 550 ${SONARQUBE_HOME}; \
    chmod -R 770 "${SQ_DATA_DIR}" "${SQ_EXTENSIONS_DIR}" "${SQ_LOGS_DIR}" "${SQ_TEMP_DIR}"; \
    apt-get remove -y gnupg unzip; \
    rm -rf /var/lib/apt/lists/*;

VOLUME ["${SQ_DATA_DIR}", "${SQ_EXTENSIONS_DIR}", "${SQ_LOGS_DIR}", "${SQ_TEMP_DIR}"]

COPY --chown=root:root --chmod=555 entrypoint.sh ${SONARQUBE_HOME}/docker/

WORKDIR ${SONARQUBE_HOME}
EXPOSE 9000

USER sonarqube
STOPSIGNAL SIGINT

ENTRYPOINT ["/opt/sonarqube/docker/entrypoint.sh"]
