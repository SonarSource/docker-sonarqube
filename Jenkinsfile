#!groovy
// This takes from the standard build a bit, and twists it for our purposes.

node {
   // Checkout the code and make some env vars we use in later builds
   stage('Checkout') {
        // Clone repo
        checkout scm

        // Set some needed env variables for later
        env.GIT_COMMIT = sh(returnStdout: true, script: 'git rev-parse HEAD').trim()
        env.PROJECT_NAME='sonarqube'
        env.GIT_BRANCH = env.BRANCH_NAME

        if (! env.DOCKER_IMAGE_BASE) {
            env.DOCKER_IMAGE_BASE = "${PROJECT_NAME}:${GIT_COMMIT}"
        }
    } 

    // We're going to build and deploy the Sonarqube version 6.6
    dir('6.6'){
        stage('Build Docker') {
            ansiColor('xterm') {
                retry(3) {
                    sh '/opt/plangrid/build-tools/bin/build-docker'
                }
            }
        }
        stage('Push Docker') {
            ansiColor('xterm') {
                retry(3) {
                    sh '/opt/plangrid/build-tools/bin/push-docker'
                }
            }
        }
    }
}

