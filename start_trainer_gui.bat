@echo off
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Get-Command pythonw -ErrorAction SilentlyContinue; if (-not $p) { $p = Get-Command python -ErrorAction SilentlyContinue }; if (-not $p) { Write-Host 'Python not found'; pause; exit 1 }; $script = '%~dp0trainer_gui.py'; Start-Process -FilePath $p.Source -ArgumentList ('"' + $script + '"') -Verb RunAs"
