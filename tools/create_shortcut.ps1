# 在当前用户桌面创建“三角债智能轧差系统”快捷方式。
$ErrorActionPreference = "Stop"

$project = Split-Path -Parent $PSScriptRoot
$vbs = Join-Path $project "启动债务轧差系统.vbs"
$icon = Join-Path $project "assets\app.ico"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "三角债智能轧差系统.lnk"

if (-not (Test-Path $vbs)) {
    throw "未找到启动脚本：$vbs"
}
if (-not (Test-Path $icon)) {
    throw "未找到图标文件：$icon"
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $env:SystemRoot "System32\wscript.exe"
$shortcut.Arguments = '"' + $vbs + '"'
$shortcut.WorkingDirectory = $project
$shortcut.IconLocation = "$icon,0"
$shortcut.Description = "启动三角债智能梳理与净额轧差系统"
$shortcut.WindowStyle = 1
$shortcut.Save()

Write-Host "已创建桌面快捷方式：$shortcutPath"
