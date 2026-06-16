# CineLang AI stack setup — PostgreSQL+pgvector + Ollama + Gemma 3 4B
# Run from D:\startup\cinelang\
# Requires: Docker Desktop running

Write-Host "=== CineLang AI Setup ===" -ForegroundColor Cyan

# 1. Start containers
Write-Host "`n[1/4] Starting PostgreSQL+pgvector and Ollama containers..." -ForegroundColor Yellow
docker compose -f docker-compose.ai.yml up -d

# 2. Wait for Postgres
Write-Host "`n[2/4] Waiting for PostgreSQL to be ready..." -ForegroundColor Yellow
$retries = 0
do {
    Start-Sleep -Seconds 2
    $ready = docker exec cinelang_postgres pg_isready -U cinelang 2>&1
    $retries++
    Write-Host "  attempt $retries : $ready"
} while ($ready -notlike "*accepting connections*" -and $retries -lt 20)

if ($retries -ge 20) {
    Write-Host "PostgreSQL did not start in time." -ForegroundColor Red
    exit 1
}
Write-Host "  PostgreSQL ready!" -ForegroundColor Green

# 3. Pull Gemma 3 4B (large download — ~2.5 GB)
Write-Host "`n[3/4] Pulling gemma3:4b model (may take several minutes)..." -ForegroundColor Yellow
docker exec cinelang_ollama ollama pull gemma3:4b

# 4. Pull embedding model
Write-Host "`n[4/4] Pulling nomic-embed-text embedding model..." -ForegroundColor Yellow
docker exec cinelang_ollama ollama pull nomic-embed-text

Write-Host "`n=== Done! ===" -ForegroundColor Green
Write-Host "PostgreSQL : localhost:5432  (user=cinelang  pass=cinelang_secret  db=cinelang)"
Write-Host "Ollama     : http://localhost:11434"
Write-Host "Models     : gemma3:4b, nomic-embed-text"
Write-Host ""
Write-Host "Test endpoints:"
Write-Host "  GET  http://localhost:8000/api/ai/status"
Write-Host "  POST http://localhost:8000/api/ai/enrich   {word, context, source_lang, target_lang}"
Write-Host "  POST http://localhost:8000/api/ai/analyse  {text, lang}"
