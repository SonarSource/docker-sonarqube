#!/bin/bash

set -euo pipefail

docker build -t sonarsource/sonar-5.6.1 5.6.1
docker build -t sonarsource/sonar-5.6.1-alpine 5.6.1-alpine
