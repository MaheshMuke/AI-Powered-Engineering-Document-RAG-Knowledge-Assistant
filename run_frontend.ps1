# run_frontend.ps1
# Sets PYTHONPATH so Python can find the frontend and backend packages
$env:PYTHONPATH = $PSScriptRoot
Write-Host "Starting Streamlit frontend..." -ForegroundColor Cyan
.venv\Scripts\python.exe -m streamlit run frontend/app.py
