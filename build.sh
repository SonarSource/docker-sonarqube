#!/bin/bash

set -euo pipefail

docker build -t sonarsource/sonar-4.5.6 4.5.6
docker build -t sonarsource/sonar-5.1.2 5.1.2
docker build -t sonarsource/sonar-5.2 5.2
