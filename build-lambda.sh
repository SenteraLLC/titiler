#!/usr/bin/env bash

# This script compiles the service into a Python Lambda build artifact

set -ex

PROJ_DIR=$(git rev-parse --show-toplevel)
BUILD_DIR=${PROJ_DIR}/build
DOCKER_TAG=titiler_build
LAMBDA_PATH=${PROJ_DIR}/package.zip

cd ${PROJ_DIR}

# Clean out old build relics
rm -rf ${BUILD_DIR}
mkdir -p $(dirname ${BUILD_DIR})
rm -f ${LAMBDA_PATH}
mkdir -p $(dirname ${LAMBDA_PATH})

# Build Docker image and copy build assets out:
docker build --no-cache -f ${PROJ_DIR}/deployment/aws/lambda/Dockerfile -t ${DOCKER_TAG} .
docker run --rm -it -v ${BUILD_DIR}:/asset-output --entrypoint /bin/bash ${DOCKER_TAG} -c 'cp -R /asset/. /asset-output/.'

# Package up into .zip:
cd ${BUILD_DIR}
zip -r ${LAMBDA_PATH} .
