#!/bin/bash

set -euo pipefail

docker build -t sonarsource/sonar-4.5.7 4.5.7
docker build -t sonarsource/sonar-5.5 5.5

docker build -t sonarsource/sonar-4.5.7-alpine 4.5.7-alpine
docker build -t sonarsource/sonar-5.5-alpine 5.5-alpine
