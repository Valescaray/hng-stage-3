#!/bin/bash
# Usage: ./scripts/simulate_attack.sh YOUR_SERVER_IP

TARGET=${1:-"localhost"}
echo "Simulating single-IP attack on $TARGET..."
ab -n 1000 -c 100 http://$TARGET/

echo ""
echo "Simulating global traffic flood (many fake IPs)..."
for i in $(seq 1 20); do
  curl -s -o /dev/null \
    -H "X-Forwarded-For: 10.0.$((RANDOM % 255)).$((RANDOM % 255))" \
    http://$TARGET/ &
done
wait
echo "Done."
