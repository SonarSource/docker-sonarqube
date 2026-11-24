#!/bin/bash
set -e

JAVA="${JAVA_HOME}/bin/java"
DEFAULT_CMD=("$JAVA" '-jar' 'lib/sonarqube.jar' '-Dsonar.log.console=true')

# this if will check if the first argument is a flag
# but only works if all arguments require a hyphenated flag
# -v; -SL; -f arg; etc will work, but not arg1 arg2
if [[ $# -eq 0 ]] || [[ "${1#-}" != "${1}" ]]; then
    if [[ "${SONARQUBE_REQUIRE_FIPS:-}" == 1 ]]; then
        if [[ ! -r /proc/sys/crypto/fips_enabled ]] || [[ "$(cat /proc/sys/crypto/fips_enabled)" != 1 ]]; then
            echo 'SonarQube requires a FIPS-enabled host' >&2
            exit 1
        fi
        if ! providers=$("$JAVA" -XshowSettings:security:providers -version 2>&1) ||
            ! grep -q 'Provider name: SunPKCS11-FIPS' <<< "$providers"; then
            echo 'SonarQube requires the SunPKCS11-FIPS provider' >&2
            exit 1
        fi
    fi
    set -- "${DEFAULT_CMD[@]}" "$@"
fi

exec "$@"
