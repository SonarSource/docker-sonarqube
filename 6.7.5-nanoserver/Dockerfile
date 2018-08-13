FROM openjdk:nanoserver

SHELL ["powershell", "-Command", "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';"]

ENV SONARQUBE_VERSION=6.7.5 \
    SONARQUBE_HOME=C:\\sonarqube \
    # Database configuration
    # Defaults to using H2
    SONARQUBE_JDBC_USERNAME=sonar \
    SONARQUBE_JDBC_PASSWORD=sonar \
    SONARQUBE_JDBC_URL=

RUN powershell -command \
    New-Item -ItemType Directory -Force -Path $Env:SONARQUBE_HOME ; \
    $parent_dir = Split-Path -Path $Env:SONARQUBE_HOME -Parent ; \
    Set-Location -Path $parent_dir ; \
    Invoke-WebRequest "https://sonarsource.bintray.com/Distribution/sonarqube/sonarqube-$Env:SONARQUBE_VERSION.zip" -OutFile "$Env:TEMP\sonarqube.zip"; \
    Expand-Archive -Path "$Env:TEMP\sonarqube.zip" -DestinationPath $parent_dir ; \
    Remove-Item "$Env:TEMP\sonarqube.zip" ; \
    Remove-Item $Env:SONARQUBE_HOME ; \
    $target_folder_name = Split-Path $Env:SONARQUBE_HOME -Leaf ; \
    Rename-Item sonarqube-$Env:SONARQUBE_VERSION $target_folder_name ; \
    Remove-Item $Env:SONARQUBE_HOME\data\*.*

VOLUME $SONARQUBE_HOME\\data

EXPOSE 9000

WORKDIR $SONARQUBE_HOME

COPY sonarqube.cmd $SONARQUBE_HOME\\bin

ENTRYPOINT [".\\bin\\sonarqube.cmd"]
