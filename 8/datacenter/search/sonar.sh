#!/usr/bin/env bash
IP=$(ifconfig | sed -En 's/127.0.0.1//;s/.*inet (addr:)?(([0-9]*\.){3}[0-9]*).*/\2/p')
HOSTNAME=$(hostname)
if [ -z "$SONAR_PATH_LOGS" ]
then
    SONAR_CLUSTER_PATH_LOGS="logs/${HOSTNAME}"
    mkdir -p ${SONARQUBE_HOME}/${SONAR_CLUSTER_PATH_LOGS}
    chown -R sonarqube:sonarqube ${SONARQUBE_HOME}/${SONAR_CLUSTER_PATH_LOGS}
else
    SONAR_CLUSTER_PATH_LOGS="${SONAR_PATH_LOGS}/${HOSTNAME}"
    mkdir -p ${SONAR_CLUSTER_PATH_LOGS}
    chown -R sonarqube:sonarqube ${SONAR_CLUSTER_PATH_LOGS}
fi

exec java -jar lib/sonar-application-"${SONAR_VERSION}".jar -Dsonar.log.console=true -Dsonar.log.console=true -Dsonar.cluster.node.search.host=${IP} -Dsonar.cluster.node.es.host=${IP} -Dsonar.cluster.node.host=${IP} -Dsonar.path.logs=${SONAR_CLUSTER_PATH_LOGS} "$@"
