#!/bin/bash
echo "🛑 Остановка бота..."
PID=$(ps aux | grep '[b]ot.py' | awk '{print $2}')
if [ -z "$PID" ]; then
  echo "Бот не запущен."
else
  kill -9 $PID
  echo "Бот остановлен (PID $PID)."
fi