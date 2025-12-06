@echo off
REM Activate the Python virtual environment
call "D:/Work/Programming/Python project/Projects/Intratrade Helper/.venv/Scripts/activate.bat"

REM Run the Streamlit application
streamlit run app_streamlit.py

REM Keep window open after exit
pause
