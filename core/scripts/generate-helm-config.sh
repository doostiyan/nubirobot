#!/bin/bash

HELM_BIN=("microk8s" "helm")
"${HELM_BIN[@]}" template $1 # path to helm package folder
