#!/bin/bash
set -e

export SONAR_JDBC_URL=$(yq .SONAR_JDBC_URL /configs/config.yaml )
export SONAR_JDBC_USERNAME=$(yq .SONAR_JDBC_USERNAME /configs/config.yaml )
export SONAR_JDBC_PASSWORD=$(yq .SONAR_JDBC_PASSWORD /configs/config.yaml )

DEFAULT_CMD=('/opt/java/openjdk/bin/java' '-jar' 'lib/sonarqube.jar' '-Dsonar.log.console=true' "-Dsonar.jdbc.url=${SONAR_JDBC_URL}" "-Dsonar.jdbc.username=${SONAR_JDBC_USERNAME}" "-Dsonar.jdbc.password=${SONAR_JDBC_PASSWORD}")

# this if will check if the first argument is a flag
# but only works if all arguments require a hyphenated flag
# -v; -SL; -f arg; etc will work, but not arg1 arg2
if [ "$#" -eq 0 ] || [ "${1#-}" != "$1" ]; then
    set -- "${DEFAULT_CMD[@]}" "$@"
fi

exec "$@"
