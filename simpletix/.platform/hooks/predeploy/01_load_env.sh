#!/bin/bash
set -e

echo "Loading EB environment variables..."
eval "$(/opt/elasticbeanstalk/bin/get-config environment | jq -r 'to_entries | map("export \(.key)=\(.value|tostring)") | .[]')"
