#!/usr/bin/env bash
set -e

# If passed arguments execute that instead of this file
if [ "${1:0:1}" != '-' ]; then
  exec "$@"
fi

properties_file=conf/sonar.properties
# Make sure propfile ends with newline
if [[ "$(tail -c1 "$properties_file" | wc -l)" -eq 0 ]]; then echo "" >> "$properties_file"; fi

# usage: set_prop java.property value
#    ie: set_prop sonar.jdbc.username sonar
# Will set named property in $properties_file, will update or add
set_prop() {
    
    local prop="$1"
    local val="$2"

    # Escaped for sed/grep usage
    local prop_escaped=$(echo $prop | sed 's/[]\/$*.^[]/\\&/g')
    local val_escaped=$(echo $val | sed -e 's/[\/&]/\\&/g')
    
    if grep -q "^\s*${prop_escaped}=.*$" "$properties_file"; then 
        # Property found in file, replace to correct value
        sed -i "s/^\(${prop_escaped}=\).*\$/\1${val_escaped}/g" "$properties_file"
    else 
        # Property does not exist in file, add it the the end
        echo "${prop}=${val}" >> "$properties_file"
    fi
    
}

# usage: create_prop_from_secret java.property secret-file
#    ie: create_prop_from_secret sonar.jdbc.password /run/secrets/postgres-passwd
# Reads secret-file and sets java.property with the contents
function create_prop_from_secret() {

    local val
    if [ "${!2:-}" ]; then
        val="$(< "${!2}")"
        set_prop "$1" "$val"
    fi

}

# Parse Docker env vars to customize SonarQube
#
# e.g. Setting the env var sonar.jdbc.username=foo
#
# will add or update named property in conf/sonar.properties
while IFS='=' read -r envvar_key envvar_value
do
    if [[ "$envvar_key" =~ sonar\..* ]] || [[ "$envvar_key" =~ ldap\..* ]]; then
        set_prop "${envvar_key}" "${envvar_value}"
    fi
done < <(env)

# Try to set known secrets as java properties, will skip if FILE var is not set
create_prop_from_secret "sonar.jdbc.password" "SONAR_JDBC_PASSWORD_FILE"
create_prop_from_secret "ldap.bindPassword" "LDAP_BINDPASSWORD_FILE"
create_prop_from_secret "http.proxyPassword" "HTTP_PROXYPASSWORD_FILE"

exec java -jar lib/sonar-application-$SONAR_VERSION.jar \
  -Dsonar.log.console=true \
  -Dsonar.web.javaAdditionalOpts="$SONARQUBE_WEB_JVM_OPTS -Djava.security.egd=file:/dev/./urandom" \
  "$@"
