param([switch]$Direct)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$ollamaCommand=Get-Command ollama -ErrorAction SilentlyContinue
$ollamaBinary=if ($ollamaCommand) { $ollamaCommand.Source } else { Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe' }
if (-not (Test-Path -LiteralPath $ollamaBinary)) { throw 'Installed Ollama executable not found; install/configure it explicitly.' }
try {
    $existing=Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -NoProxy -TimeoutSec 2
    Write-Output ('Existing local Ollama is available: '+$existing.version+'. Verify the approved model digest before use.')
    return
} catch { }
$modelDirectory=Join-Path $projectRoot 'model-cache\ollama'
$logDirectory=Join-Path $projectRoot 'artifacts\ollama'
New-Item -ItemType Directory -Force -Path $modelDirectory,$logDirectory | Out-Null
$settings=@{OLLAMA_MODELS=$modelDirectory;OLLAMA_HOST='127.0.0.1:11434';OLLAMA_NO_CLOUD='1';OLLAMA_NUM_PARALLEL='1';OLLAMA_MAX_LOADED_MODELS='1'}
if ($Direct) { $settings['HTTPS_PROXY']='';$settings['HTTP_PROXY']='' }
$savedSettings=@{}
try {
    foreach ($name in $settings.Keys) { $savedSettings[$name]=[Environment]::GetEnvironmentVariable($name,'Process');[Environment]::SetEnvironmentVariable($name,$settings[$name],'Process') }
    $ollamaProcess=Start-Process -FilePath $ollamaBinary -ArgumentList 'serve' -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logDirectory 'server.stdout.log') -RedirectStandardError (Join-Path $logDirectory 'server.stderr.log')
    Write-Output ('Local Ollama started; PID '+$ollamaProcess.Id+'. Model cache and logs are ignored by Git. No model was pulled automatically.')
} finally {
    foreach ($name in $savedSettings.Keys) { [Environment]::SetEnvironmentVariable($name,$savedSettings[$name],'Process') }
}
