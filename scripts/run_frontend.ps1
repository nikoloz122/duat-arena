# Start the Next.js dashboard on port 3000 (primary demo UI).
# Only ONE frontend dev server should run — a second instance binds to :3001
# and causes confusion if you open localhost:3000.

$existing = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host ""
    Write-Host "ERROR: Port 3000 is already in use (PID $($existing[0].OwningProcess))." -ForegroundColor Red
    Write-Host "Stop the other npm run dev process first. Use only ONE frontend at http://localhost:3000"
    Write-Host "See README Troubleshooting -> Port conflicts."
    exit 1
}

Push-Location frontend
npm run dev
Pop-Location
