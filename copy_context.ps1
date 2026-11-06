# ==============================================================================
# NOVA 2.0 — Ultra-Compact Claude AI Context Copier (~1,200 tokens)
# Copies complete architectural and technical briefing directly to clipboard.
# ==============================================================================
$ErrorActionPreference = "SilentlyContinue"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
if (-not $scriptDir) { $scriptDir = (Get-Location).Path }

$claudeFile = Join-Path $scriptDir "CLAUDE.md"
if (-not (Test-Path $claudeFile)) {
    Write-Host "[ERROR] CLAUDE.md not found at $claudeFile" -ForegroundColor Red
    exit 1
}

$gitBranch = (git -C $scriptDir branch --show-current 2>$null)
if (-not $gitBranch) { $gitBranch = "main" } else { $gitBranch = $gitBranch.Trim() }

$gitCommit = (git -C $scriptDir log -1 --oneline 2>$null)
if (-not $gitCommit) { $gitCommit = "latest" } else { $gitCommit = $gitCommit.Trim() }

$claudeContent = Get-Content $claudeFile -Raw -Encoding UTF8

$header = "<!-- NOVA 2.0 AI AGENT CONTEXT BRIEFING -->`r`n<!-- Git Branch: $gitBranch | Last Commit: $gitCommit -->`r`n<!-- Paste this entire block into a new Claude chat. Consumes ~1,200 tokens. -->`r`n`r`n"

$fullPayload = $header + $claudeContent
Set-Clipboard -Value $fullPayload

$wordCount = ($fullPayload -split '\s+').Count
$approxTokens = [math]::Round($wordCount * 1.3)
$charCount = $fullPayload.Length

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   NOVA 2.0 -- Context Copied to Clipboard Successfully!   " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ("   Size: ~" + $approxTokens + " tokens | " + $wordCount + " words | " + $charCount + " characters") -ForegroundColor Gray
Write-Host ("   Git:  Branch: " + $gitBranch + " | Commit: " + $gitCommit) -ForegroundColor DarkGray
Write-Host ""
Write-Host ">> Ab Claude (ya kisi bhi AI chat) mein jaakar Ctrl + V dabao!" -ForegroundColor Yellow
Write-Host ""
