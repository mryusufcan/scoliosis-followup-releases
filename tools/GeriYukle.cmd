@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -NoExit -Command "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); & '%~dp0restore_point.ps1' -List; $tag = Read-Host 'Geri yuklenecek etiket'; if (-not [string]::IsNullOrWhiteSpace($tag)) { & '%~dp0restore_point.ps1' -Tag $tag }"
