#!/usr/bin/env bash

set -eou pipefail

if [[ "${1:-}" != -* ]]; then
  exec "$@" 
fi

declare -a sq_opts

add_env_var_as_env_prop() {
  if [ ! -z "$1" ]; then
    sq_opts+=("-D$2=$1")
  fi
}

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
# map legacy env variables
add_env_var_as_env_prop "${SONARQUBE_JDBC_USERNAME:-}" "sonar.jdbc.username"
add_env_var_as_env_prop "${SONARQUBE_JDBC_PASSWORD:-}" "sonar.jdbc.password"
add_env_var_as_env_prop "${SONARQUBE_JDBC_URL:-}" "sonar.jdbc.url"
add_env_var_as_env_prop "${SONARQUBE_WEB_JVM_OPTS:-}" "sonar.web.javaAdditionalOpts"

exec java -jar "lib/sonar-application-$SONAR_VERSION.jar" \
  -Dsonar.log.console=true \
  "${sq_opts[@]}" \
  "$@"
