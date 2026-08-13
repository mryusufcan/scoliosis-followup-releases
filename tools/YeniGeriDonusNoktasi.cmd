@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -NoExit -Command "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); $message = Read-Host 'Kisa aciklama (bos birakabilirsiniz)'; if ([string]::IsNullOrWhiteSpace($message)) { $message = 'Calisan surum' }; & '%~dp0create_restore_point.ps1' -Message $message"
