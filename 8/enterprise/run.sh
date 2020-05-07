#!/usr/bin/env bash

set -euo pipefail

declare -a sq_opts=()
set_prop_from_deprecated_env_var() {
  if [ "$2" ]; then
    sq_opts+=("-D$1=$2")
  fi
}

# if nothing is passed, assume we want to run sonarqube server
if [ "$#" == 0 ]; then
  set -- bin/sonar.sh
fi

# if first arg looks like a flag, assume we want to run sonarqube server with flags
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

    #
    # Deprecated way to pass settings to SonarQube that will be removed in future versions.
    # Please use environment variables (https://docs.sonarqube.org/latest/setup/environment-variables/)
    # instead to customize SonarQube.
    #
    while IFS='=' read -r envvar_key envvar_value
    do
        if [[ "$envvar_key" =~ sonar.* ]] || [[ "$envvar_key" =~ ldap.* ]]; then
            sq_opts+=("-D${envvar_key}=${envvar_value}")
        fi
    done < <(env)

    #
    # Deprecated environment variable mapping that will be removed in future versions.
    # Please use environment variables from https://docs.sonarqube.org/latest/setup/environment-variables/
    # instead of using these 4 environment variables below.
    #
    set_prop_from_deprecated_env_var "sonar.jdbc.username" "${SONARQUBE_JDBC_USERNAME:-}"
    set_prop_from_deprecated_env_var "sonar.jdbc.password" "${SONARQUBE_JDBC_PASSWORD:-}"
    set_prop_from_deprecated_env_var "sonar.jdbc.url" "${SONARQUBE_JDBC_URL:-}"
    set_prop_from_deprecated_env_var "sonar.web.javaAdditionalOpts" "${SONARQUBE_WEB_JVM_OPTS:-}"
    if [ ${#sq_opts[@]} -ne 0 ]; then
        set -- "$@" "${sq_opts[@]}"
    fi
fi

exec "$@"
