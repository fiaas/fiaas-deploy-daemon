#!/usr/bin/env bash

echo "... checking for API key ..."
if [[ -z "${DD_API_KEY}" ]]; then
    echo "You must export the Datadog API key as DD_API_KEY for this script to work!"
    exit 1
fi

echo "... starting minikube ..."
minikube start

SCRIPT_DIR="$(dirname "${0}")"

echo "... injecting secrets ..."
"${SCRIPT_DIR}/inject_pull_secret"
kubectl create secret generic datadog --from-literal apikey="${DD_API_KEY}"

sleep 5 && \
    echo "... deploying datadog-test ..." && \
    kubectl create -f "${SCRIPT_DIR}/datadog-test.yaml" &

echo "... starting fiaas-deploy-daemon ..."
"${SCRIPT_DIR}/run_fdd_against_minikube"
