#!/bin/bash

set -euo pipefail

docker build -t sonarsource/sonar-5.6 5.6
docker build -t sonarsource/sonar-5.6-alpine 5.6-alpine
