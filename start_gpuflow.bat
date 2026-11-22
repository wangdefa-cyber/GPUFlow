@echo off
chcp 65001 >nul
setlocal
title GPUFlow v1.0
cd /d "%~dp0"

echo ============================================================
echo   GPUFlow v1.0 - GPU resource scheduling simulator
echo ============================================================
echo.

set "CONDA_ACTIVATE=D:\anaconda3\Scripts\activate.bat"
if exist "%CONDA_ACTIVATE%" goto activate_conda

where conda >nul 2>&1
if errorlevel 1 goto conda_missing

call conda activate gpu_analysis
goto check_environment

:activate_conda
call "%CONDA_ACTIVATE%" gpu_analysis
if errorlevel 1 goto env_missing

:check_environment
python -c "import streamlit, pandas, sqlalchemy, plotly" >nul 2>&1
if errorlevel 1 goto dependencies_missing

echo Starting GPUFlow...
echo Browser address: http://localhost:8501
echo Close this window to stop the application.
echo.

set "GPUFLOW_ARGS="
if /I "%GPUFLOW_HEADLESS%"=="1" set "GPUFLOW_ARGS=--server.headless=true --server.address=127.0.0.1 --server.port=8768 --server.enableAgentApi=true"

python -m streamlit run "%~dp0streamlit_app.py" %GPUFLOW_ARGS%
if errorlevel 1 goto run_failed
goto end

:conda_missing
echo [ERROR] Conda was not found.
echo Install Anaconda or add conda to PATH, then run this file again.
pause
exit /b 1

:env_missing
echo [ERROR] Conda environment "gpu_analysis" could not be activated.
echo Create it with:
echo     conda env create -f environment.yml
pause
exit /b 1

:dependencies_missing
echo [ERROR] Required Python packages are missing from "gpu_analysis".
echo Repair the environment with:
echo     conda env update -n gpu_analysis -f environment.yml
pause
exit /b 1

:run_failed
echo.
echo [ERROR] GPUFlow stopped because Streamlit returned an error.
pause
exit /b 1

:end
endlocal
