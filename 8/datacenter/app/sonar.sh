#!/usr/bin/env bash
IP=$(ifconfig | sed -En 's/127.0.0.1//;s/.*inet (addr:)?(([0-9]*\.){3}[0-9]*).*/\2/p')
exec java -jar lib/sonar-application-"${SONAR_VERSION}".jar -Dsonar.log.console=true -Dsonar.log.console=true -Dsonar.cluster.node.host=${IP} "$@"
