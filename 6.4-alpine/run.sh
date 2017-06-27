#!/bin/sh

set -e

if [ "${1:0:1}" != '-' ]; then
  exec "$@"
fi

#Install additional plugins
SONAR_PLUGIN_DIR="/opt/sonarqube/extensions/plugins"
NUMBER_OF_PLUGINS=$(($((`echo $SONARQUBE_PLUGIN_LIST | sed 's/[^,]//g' | wc -c` - 1 ))+1))
for i in $(seq 1 $NUMBER_OF_PLUGINS);
do
    #Extract plugin name and version
    pluginName=$(echo "$SONARQUBE_PLUGIN_LIST" | cut -d, -f$i | cut -d: -f1)
    pluginVersion=$(echo "$SONARQUBE_PLUGIN_LIST" | cut -d, -f$i | cut -d: -f2)
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
    wget -O $SONAR_PLUGIN_DIR/$pluginName-$pluginVersion.jar --no-verbose "https://sonarsource.bintray.com/Distribution/$pluginName/$pluginName-$pluginVersion.jar"
done

#Run sonar
exec java -jar lib/sonar-application-$SONAR_VERSION.jar \
  -Dsonar.log.console=true \
  -Dsonar.jdbc.username="$SONARQUBE_JDBC_USERNAME" \
  -Dsonar.jdbc.password="$SONARQUBE_JDBC_PASSWORD" \
  -Dsonar.jdbc.url="$SONARQUBE_JDBC_URL" \
  -Dsonar.web.javaAdditionalOpts="$SONARQUBE_WEB_JVM_OPTS -Djava.security.egd=file:/dev/./urandom" \
  "$@"