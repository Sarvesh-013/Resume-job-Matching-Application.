@echo off
echo Starting Zookeeper...
cd /d C:\kafka
start cmd /k "zookeeper-server-start.bat C:\kafka\config\zookeeper.properties"

:: Wait for 10 seconds to ensure Zookeeper starts
timeout /t 10 /nobreak >nul

echo Starting Kafka...
start cmd /k "kafka-server-start.bat C:\kafka\config\server.properties"

:: Wait for Kafka to start
timeout /t 10 /nobreak >nul

echo Starting Resume Processing Service...
cd /d D:\Projects\Job_Predictor
start cmd /k "call Job\Scripts\activate && python resume_processor.py"

:: Wait for a few seconds
timeout /t 5 /nobreak >nul

echo Starting Web Application...
start cmd /k "call Job\Scripts\activate && python app.py"

echo All services started successfully!
