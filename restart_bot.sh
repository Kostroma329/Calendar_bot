#!/bin/bash
# Переходим в папку бота (на всякий случай)
cd /home/Kostroma/calendar_bot

# Останавливаем старый процесс
pkill -f "python3.10 bot.py"
sleep 2

# Запускаем новый
nohup python3.10 bot.py > bot.log 2>&1 &

echo "Bot restarted successfully"
echo "Check logs: tail -f bot.log"