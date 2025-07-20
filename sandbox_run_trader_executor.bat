@echo off
cd /d "C:\PY_Project\PY\!_01_prj_BolingerBands\!_BB_project_5_TradingBot"
chcp 65001 > nul

:: Явное указание пути к python.exe
"C:\Users\pavel\anaconda3\python.exe" trader_executor.py >> log_trader_executor.txt 2>&1
