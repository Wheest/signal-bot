#!/usr/bin/env sh
socat - UNIX-CONNECT:$SIGNALD_SOCKET_PATH &

while true; do
  echo "src/bot.py" | entr -nr sh -c 'python3 src/bot.py'
  echo "Bot script exited. Restarting in 2 seconds..."
  sleep 2
done
