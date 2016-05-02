#!/bin/bash

set -euo pipefail

docker build -t sonarsource/sonar-4.5.7 4.5.7
docker build -t sonarsource/sonar-5.4 5.4

docker build -t sonarsource/sonar-4.5.7-alpine 4.5.7-alpine
docker build -t sonarsource/sonar-5.4-alpine 5.4-alpine
