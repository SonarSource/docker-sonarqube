#!/bin/bash
set -e

DEFAULT_CMD=('/opt/java/openjdk/bin/java' '-jar' 'lib/sonarqube.jar' '-Dsonar.log.console=true')

# this if will check if the first argument is a flag
# but only works if all arguments require a hyphenated flag
# -v; -SL; -f arg; etc will work, but not arg1 arg2
if [ "$#" -eq 0 ] || [ "${1#-}" != "$1" ]; then
    set -- "${DEFAULT_CMD[@]}" "$@"
fi

exec "$@"
