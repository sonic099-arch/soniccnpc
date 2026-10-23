param(
    [string]$ListenAddress = "10.86.36.43",
    [int]$Port = 8080
)
$ErrorActionPreference = "Stop"
# 此脚本只管理本应用自己的防火墙规则，不关闭防火墙，也不修改其他规则。
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "请使用管理员PowerShell运行：首次配置或更新Windows防火墙规则需要管理员权限。"
}
if (-not (Get-NetIPAddress -AddressFamily IPv4 -IPAddress $ListenAddress -ErrorAction SilentlyContinue)) {
    throw "Windows网卡没有地址 $ListenAddress，请先确认电脑IP。"
}
try {
    $ready = Invoke-RestMethod -Uri "http://127.0.0.1:8000/ready" -TimeoutSec 10
    $page = Invoke-WebRequest -Uri "http://127.0.0.1:8000/" -UseBasicParsing -TimeoutSec 10
    if ($ready.status -ne "ok" -or $page.StatusCode -ne 200 -or $page.Content -notmatch '<html') {
        throw "服务尚未准备好"
    }
} catch {
    throw "Windows无法访问本机后端。请先在Ubuntu运行 python scripts/lan.py，再在Windows打开 http://localhost:8000 确认可用。无需netsh端口转发。"
}
$ruleName = "BeitianGasLAN-$Port"
if (Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue) {
    Remove-NetFirewallRule -Name $ruleName | Out-Null
}
New-NetFirewallRule -Name $ruleName -DisplayName "北田气井内网入口 $Port" `
    -Direction Inbound -Action Allow -Protocol TCP -LocalAddress $ListenAddress -LocalPort $Port `
    -RemoteAddress "10.86.36.1-10.86.36.255" -Profile Any | Out-Null
Write-Host "防火墙已限定来源 10.86.36.1–10.86.36.255，内网地址 http://${ListenAddress}:$Port"
$gateway = Join-Path $PSScriptRoot "lan_gateway.py"
if (-not (Test-Path $gateway)) { throw "缺少同目录下的lan_gateway.py，请同时复制两个脚本。" }
if (Get-Command py.exe -ErrorAction SilentlyContinue) {
    & py.exe -3 $gateway --listen $ListenAddress --port $Port
} elseif (Get-Command python.exe -ErrorAction SilentlyContinue) {
    & python.exe $gateway --listen $ListenAddress --port $Port
} else {
    throw "Windows需要安装Python 3.12或3.14并启用py启动器；网关只用标准库，不安装业务依赖。"
}
if ($LASTEXITCODE -ne 0) { throw "内网入口启动失败，请查看上方错误。" }
