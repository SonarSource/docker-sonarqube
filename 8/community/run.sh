#!/usr/bin/env bash

set -euo pipefail


declare -a sq_opts
set_prop_from_env_var() {
  if [ "$2" ]; then
    sq_opts+=("-D$1=$2")
  fi
}

# if first arg looks like a flag, assume we want to run sonarqube server
if [ "${1:0:1}" = '-' ]; then
    set -- bin/sonar.sh "$@"
fi

if [[ "$1" = 'bin/sonar.sh' ]]; then
    chown -R "$(id -u):$(id -g)" "${SQ_DATA_DIR}" "${SQ_EXTENSIONS_DIR}" "${SQ_LOGS_DIR}" "${SQ_TEMP_DIR}" 2>/dev/null || :
    chmod -R 700 "${SQ_DATA_DIR}" "${SQ_EXTENSIONS_DIR}" "${SQ_LOGS_DIR}" "${SQ_TEMP_DIR}" 2>/dev/null || :

    # Allow the container to be started with `--user`
    if [[ "$(id -u)" = '0' ]]; then
        chown -R sonarqube:sonarqube "${SQ_DATA_DIR}" "${SQ_EXTENSIONS_DIR}" "${SQ_LOGS_DIR}" "${SQ_TEMP_DIR}"
        exec su-exec sonarqube "$0" "$@"
    fi

    # Legacy setting parsing to customize SonarQube. Please use environment variables instead.
    while IFS='=' read -r envvar_key envvar_value
    do
        if [[ "$envvar_key" =~ sonar.* ]] || [[ "$envvar_key" =~ ldap.* ]]; then
            sq_opts+=("-D${envvar_key}=${envvar_value}")
            echo "read entry: ${sq_opts[*]}"
        fi
    done < <(env)

    # map legacy env variables
    set_prop_from_env_var "sonar.jdbc.username" "${SONARQUBE_JDBC_USERNAME:-}"
    set_prop_from_env_var "sonar.jdbc.password" "${SONARQUBE_JDBC_PASSWORD:-}"
    set_prop_from_env_var "sonar.jdbc.url" "${SONARQUBE_JDBC_URL:-}"
    set_prop_from_env_var "sonar.web.javaAdditionalOpts" "${SONARQUBE_WEB_JVM_OPTS:-}"
    set -- "$@" "${sq_opts[*]}"
fi

exec "$@"