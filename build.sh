#!/bin/bash

set -euo pipefail

docker build -t sonarsource/sonar-5.6.7 5.6.7
docker build -t sonarsource/sonar-5.6.7-alpine 5.6.7-alpine
docker build -t sonarsource/sonar-6.6 6.6
docker build -t sonarsource/sonar-6.6-alpine 6.6-alpine
