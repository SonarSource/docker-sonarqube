This repository contains the sources of the soon to be official SonarQube docker images.

Until the official images are deployed, you run some tests with the following procedure:

# Install docker

+ On Linux, read official install documentation: https://docs.docker.com/installation/
+ On OSX, it's easiest to use all-in-one packages: https://github.com/boot2docker/osx-installer/releases
+ On windows, I'd be happy to know if all-in-one packages are full featured now: https://github.com/boot2docker/windows-installer/releases

# Make sure docker is running

```
$ docker ps
CONTAINER ID        IMAGE               COMMAND             CREATED             STATUS              PORTS               NAMES
```

On OSX and windows, you might have to make sure `boot2docker` is up and running.

```
boot2docker init
boot2docker up
```

# Build the images

This is mandatory until the images are deployed on the Docker Hub.

```
git clone https://github.com/dgageot/docker-sonarqube.git
cd docker-sonarqube
docker build -t sonarqube:5.1 -t sonarqube:latest 5.1
docker build -t sonarqube:4.5.4 -t sonarqube:lts 4.5.4
```

# Run SonarQube

Now that the images are built, take a look at the [README.md](README.md) which
will become the official docker documentation.
