#!/bin/bash

set -euo pipefail

docker build -t sonarsource/sonar-5.6.6 5.6.6
docker build -t sonarsource/sonar-5.6.6-alpine 5.6.6-alpine
docker build -t sonarsource/sonar-6.2 6.2
docker build -t sonarsource/sonar-6.2-alpine 6.2-alpine
