#!/bin/bash

set -euo pipefail

docker build -t sonarsource/sonar-4.5.7 4.5.7
docker build -t sonarsource/sonar-5.1.2 5.1.2
docker build -t sonarsource/sonar-5.2 5.2
docker build -t sonarsource/sonar-5.3 5.3
docker build -t sonarsource/sonar-5.4 5.4

docker build -t sonarsource/sonar-4.5.7-alpine 4.5.7-alpine
docker build -t sonarsource/sonar-5.4-alpine 5.4-alpine
