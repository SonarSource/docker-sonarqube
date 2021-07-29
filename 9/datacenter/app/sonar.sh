#!/usr/bin/env bash
# JVM args needed for hazelcast
exec java --add-exports=java.base/jdk.internal.ref=ALL-UNNAMED --add-opens=java.base/java.lang=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED --add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.management/sun.management=ALL-UNNAMED --add-opens=jdk.management/com.sun.management.internal=ALL-UNNAMED -jar lib/sonar-application-"${SONAR_VERSION}".jar -Dsonar.log.console=true "$@"
