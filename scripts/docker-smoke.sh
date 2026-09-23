#!/usr/bin/env bash
set -euo pipefail

image="wind-app:smoke"
container="wind-app-smoke-${RANDOM}"

cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker build -t "$image" .
docker run -d --name "$container" -p 127.0.0.1::8000 "$image" >/dev/null
port="$(docker port "$container" 8000/tcp | awk -F: '{print $NF}')"
base_url="http://127.0.0.1:${port}"

for _ in $(seq 1 30); do
  if curl --fail --silent "${base_url}/api/ready" >/dev/null; then
    curl --fail --silent "${base_url}/" >/dev/null
    exit 0
  fi
  sleep 1
done

docker logs "$container"
exit 1
