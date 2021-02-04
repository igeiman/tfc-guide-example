#!/bin/bash

if [ ! -z "$DEBUG" ]; then
  echo "==== debug output ======================="
  echo "==== Unsorted environmetns varaible: ===="
  env
  echo "========================================="
  echo "==== TF_VAR_ environmetns varaible: ====="
  env | grep TF_VAR
  echo "==== end of debug output ================"
fi