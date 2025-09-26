#!/bin/bash
set -e

if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <filepath> <expiration_days> <service>"
    exit 1
fi

filepath=$1
expiration_days=$2
service=$3

if [ ! -f "$filepath" ]; then
    echo "File \"$filepath\" does not exist"
    exit 1
fi

tokenId=$(xxd -u -l 16 -p /dev/urandom)

if [[ "$OSTYPE" == "linux-gnu"* ]]; then
  # Linux
  exp=$(date -d "+$expiration_days days" +%s)
elif [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS
  exp=$(date -v +"$expiration_days"d +%s)
else
  echo "Unsupported OS: $OSTYPE"
  exit 1
fi

header='{"alg":"RS256","typ":"JWT"}'
payload="{\"jti\":\"$tokenId\",\"exp\":$exp,\"service\":\"$service\"}"

header_base64=$(echo -n "$header" | openssl base64 -e -A | tr '+/' '-_' | tr -d '=')
payload_base64=$(echo -n "$payload" | openssl base64 -e -A | tr '+/' '-_' | tr -d '=')

signature=$(echo -n "$header_base64.$payload_base64" | openssl dgst -sha256 -sign "$filepath" | openssl base64 -e -A | tr '+/' '-_' | tr -d '=')

token="Bearer $header_base64.$payload_base64.$signature"

echo "$token"
