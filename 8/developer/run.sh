#!/usr/bin/env bash

set -euo pipefail

if [[ "${1:-}" != -* ]]; then
  exec "$@"
fi

declare -a sq_opts

set_prop_from_env_var() {
  if [ "$2" ]; then
    sq_opts+=("-D$1=$2")
  fi
}

# Parse Docker env vars to customize SonarQube
#
# e.g. Setting the env var sonar.jdbc.username=foo
#
# will cause SonarQube to be invoked with -Dsonar.jdbc.username=foo
while IFS='=' read -r envvar_key envvar_value
do
    if [[ "$envvar_key" =~ sonar.* ]] || [[ "$envvar_key" =~ ldap.* ]]; then
        sq_opts+=("-D${envvar_key}=${envvar_value}")
    fi
done < <(env)
# map legacy env variables
set_prop_from_env_var "sonar.jdbc.username" "${SONARQUBE_JDBC_USERNAME:-}"
set_prop_from_env_var "sonar.jdbc.password" "${SONARQUBE_JDBC_PASSWORD:-}"
set_prop_from_env_var "sonar.jdbc.url" "${SONARQUBE_JDBC_URL:-}"
set_prop_from_env_var "sonar.web.javaAdditionalOpts" "${SONARQUBE_WEB_JVM_OPTS:-}"

exec java -jar "lib/sonar-application-$SONAR_VERSION.jar" \
  -Dsonar.log.console=true \
  "${sq_opts[@]}" \
  "$@"
