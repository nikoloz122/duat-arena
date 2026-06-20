if (-not $env:DUAT_API_BASE_URL) {
    $env:DUAT_API_BASE_URL = "http://localhost:8000"
}

pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
