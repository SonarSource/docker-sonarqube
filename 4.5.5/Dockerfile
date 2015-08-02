FROM java:openjdk-8u45-jdk

MAINTAINER David Gageot <david.gageot@sonarsource.com>

ENV SONARQUBE_HOME /opt/sonarqube

# Http port
EXPOSE 9000

# H2 Database port
EXPOSE 9092

# Database configuration
# Defaults to using H2
ENV SONARQUBE_JDBC_USERNAME sonar
ENV SONARQUBE_JDBC_PASSWORD sonar
ENV SONARQUBE_JDBC_URL jdbc:h2:tcp://localhost:9092/sonar

ENV SONAR_VERSION 4.5.5

# pub   4096R/F0EA05E3 2014-06-25 [expires: 2019-06-24]
#       Key fingerprint = E5C6 7B40 77AD A450 D209  2D4D 2B2E E179 F0EA 05E3
# uid                  Thomas Vérin <thomas.verin@sonarsource.com>
# sub   4096R/A0D97B83 2014-06-25 [expires: 2019-06-24]
RUN gpg --keyserver ha.pool.sks-keyservers.net --recv-keys E5C67B4077ADA450D2092D4D2B2EE179F0EA05E3

RUN set -x \
	&& cd /opt \
	&& curl -o sonarqube.zip -fSL http://downloads.sonarsource.com/sonarqube/sonarqube-$SONAR_VERSION.zip \
	&& curl -o sonarqube.zip.asc -fSL http://downloads.sonarsource.com/sonarqube/sonarqube-$SONAR_VERSION.zip.asc \
	&& gpg --verify sonarqube.zip.asc \
	&& unzip sonarqube.zip \
	&& mv sonarqube-$SONAR_VERSION sonarqube \
	&& rm sonarqube.zip* \
	&& rm -rf $SONARQUBE_HOME/bin/*

VOLUME ["$SONARQUBE_HOME/data", "$SONARQUBE_HOME/extensions"]

WORKDIR $SONARQUBE_HOME
COPY run.sh $SONARQUBE_HOME/bin/
ENTRYPOINT ["./bin/run.sh"]
