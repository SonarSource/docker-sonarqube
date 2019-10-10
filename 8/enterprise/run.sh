#!/usr/bin/env bash

set -euo pipefail

init_only=false
SONARQUBE_HOME=/opt/sq
SONARQUBE_PUBLIC_HOME=/opt/sonarqube

if [[ "${1:-}" != -* ]]; then
  exec "$@"
fi

if [ "${1:-}" = "--init" ]; then
  init_only=true
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
declare -a sq_opts
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

is_empty_dir() {
  [ -z "$(ls -A "$1")" ]
}

initialize_sq_sub_dir() {
  local sub_dir="$1"
  local dir="$SONARQUBE_PUBLIC_HOME/${sub_dir}"

  if is_empty_dir "${dir}"; then
    cp --recursive "$SONARQUBE_HOME/${sub_dir}_save/." "${dir}/" \
      && echo "Initialized content of ${dir}" \
      || echo "Failed to initialize content of ${dir}"
  elif [ "$init_only" = true ]; then
    echo "${dir} already has content, leaving it untouched"
  fi
}

# Initialize conf and extensions dir in case they have been bound to a Docker Daemon host's filesystem directory
# or to an empty volumne which has been created prior to the 'docker run' command call
# Initialization only occurs if directory is totally empty
initialize_sq_sub_dir "conf"
initialize_sq_sub_dir "extensions"


if [ "$init_only" = false ]; then
  exec java -jar "lib/sonar-application-$SONAR_VERSION.jar" \
    -Dsonar.log.console=true \
    "${sq_opts[@]}" \
    "$@"
fi
