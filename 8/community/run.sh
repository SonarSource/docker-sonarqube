#!/usr/bin/env bash

set -e

SONARQUBE_HOME=/opt/sq 

if [ "${1:0:1}" != '-' ]; then
  exec "$@"
fi

# Parse Docker env vars to customize SonarQube
#
# e.g. Setting the env var sonar.jdbc.username=foo
#
# will cause SonarQube to be invoked with -Dsonar.jdbc.username=foo

declare -a sq_opts

while IFS='=' read -r envvar_key envvar_value
do
    if [[ "$envvar_key" =~ sonar.* ]] || [[ "$envvar_key" =~ ldap.* ]]; then
        sq_opts+=("-D${envvar_key}=${envvar_value}")
    fi
done < <(env)

is_empty_dir() {
  [ -z "$(ls -A "$1")" ]
}

initialize_sq_sub_dir() {
  local sub_dir="$1"

  if is_empty_dir "$SONARQUBE_HOME/${sub_dir}"; then
    cp --recursive "$SONARQUBE_HOME/${sub_dir}_save/." "$SONARQUBE_HOME/${sub_dir}/" \
      && echo "Initialized content of $SONARQUBE_HOME/${sub_dir}" \
      || echo "Failed to initialize content of $SONARQUBE_HOME/${sub_dir}"
  fi
}

# Initialize conf and extensions dir in case they have been bound to a Docker Daemon host's filesystem directory
# or to an empty volumne which has been created prior to the 'docker run' command call
# Initialization only occurs if directory is totally empty
initialize_sq_sub_dir "conf"
initialize_sq_sub_dir "extensions"

exec java -jar lib/sonar-application-$SONAR_VERSION.jar \
  -Dsonar.log.console=true \
  -Dsonar.jdbc.username="$SONARQUBE_JDBC_USERNAME" \
  -Dsonar.jdbc.password="$SONARQUBE_JDBC_PASSWORD" \
  -Dsonar.jdbc.url="$SONARQUBE_JDBC_URL" \
  -Dsonar.web.javaAdditionalOpts="$SONARQUBE_WEB_JVM_OPTS -Djava.security.egd=file:/dev/./urandom" \
  "${sq_opts[@]}" \
  "$@"
