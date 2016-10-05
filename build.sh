#!/bin/bash

set -euo pipefail

docker build -t sonarsource/sonar-5.6.3 5.6.3
docker build -t sonarsource/sonar-5.6.3-alpine 5.6.3-alpine
docker build -t sonarsource/sonar-6.0 6.0
docker build -t sonarsource/sonar-6.0-alpine 6.0-alpine
