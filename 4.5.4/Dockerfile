FROM java:openjdk-7u79-jre
MAINTAINER David Gageot <david.gageot@sonarsource.com>

ENV SONAR_VERSION 4.5.4
ENV SONAR_HOME /opt/sonarqube
EXPOSE 9000 9092

# Database configuration
ENV SONARQUBE_JDBC_USERNAME sonar
ENV SONARQUBE_JDBC_PASSWORD sonar
ENV SONARQUBE_JDBC_URL jdbc:h2:tcp://localhost:9092/sonar

RUN cd /opt \
	&& wget -q -O sonarqube.zip http://dist.sonar.codehaus.org/sonarqube-$SONAR_VERSION.zip \
	&& unzip sonarqube.zip \
	&& mv sonarqube-$SONAR_VERSION sonarqube \
	&& rm sonarqube.zip \
	&& rm -rf $SONAR_HOME/bin/*

COPY run.sh $SONAR_HOME/bin/run.sh
CMD $SONAR_HOME/bin/run.sh
