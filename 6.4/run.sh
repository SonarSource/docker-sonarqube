#!/bin/bash

set -e

if [ "${1:0:1}" != '-' ]; then
  exec "$@"
fi

#Install additional plugins
IFS=',' read -r -a plugins <<< "$SONARQUBE_PLUGIN_LIST"
SONAR_PLUGIN_DIR="/opt/sonarqube/extensions/plugins"
for plugin in "${plugins[@]}"
do
    #Extract plugin name and version
    IFS=':' read -r -a pluginNameAndVersion <<< "$plugin"
    pluginName=${pluginNameAndVersion[0]}
    pluginVersion=${pluginNameAndVersion[1]}
    #Skip if desired plugin version is already installed
    if [ -e $SONAR_PLUGIN_DIR/$pluginName-$pluginVersion.jar ]
    then
        echo "skipping $pluginName as it is already installed in version $pluginVersion"
        continue
    fi
    #Remove any existing artifacts with wrong version
    rm -f $SONAR_PLUGIN_DIR/$pluginName*
    #Download desired plugin
    echo "Installing $pluginName-$pluginVersion"
    curl -o $SONAR_PLUGIN_DIR/$pluginName-$pluginVersion.jar -fSL "https://sonarsource.bintray.com/Distribution/$pluginName/$pluginName-$pluginVersion.jar"
done

exec java -jar lib/sonar-application-$SONAR_VERSION.jar \
  -Dsonar.log.console=true \
  -Dsonar.jdbc.username="$SONARQUBE_JDBC_USERNAME" \
  -Dsonar.jdbc.password="$SONARQUBE_JDBC_PASSWORD" \
  -Dsonar.jdbc.url="$SONARQUBE_JDBC_URL" \
  -Dsonar.web.javaAdditionalOpts="$SONARQUBE_WEB_JVM_OPTS -Djava.security.egd=file:/dev/./urandom" \
  "$@"
