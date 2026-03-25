param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$Login = "",
    [string]$Password = ""
)

$ErrorActionPreference = "Stop"

function Write-Check {
    param(
        [string]$Name,
        [bool]$Ok,
        [string]$Details = ""
    )

    if ($Ok) {
        Write-Host "[OK]  $Name $Details"
    } else {
        Write-Host "[FAIL] $Name $Details"
    }
}

function Invoke-JsonRequest {
    param(
        [string]$Method,
        [string]$Url,
        [hashtable]$Headers = @{},
        $Body = $null
    )

    $params = @{
        Method      = $Method
        Uri         = $Url
        Headers     = $Headers
        ErrorAction = "Stop"
    }

    if ($null -ne $Body) {
        $params["ContentType"] = "application/json"
        $params["Body"] = ($Body | ConvertTo-Json -Depth 10)
    }

    return Invoke-RestMethod @params
}

$base = $BaseUrl.TrimEnd("/")
$failed = $false
$token = ""

try {
    $health = Invoke-JsonRequest -Method "GET" -Url "$base/health"
    $ok = ($health.status -eq "ok")
    Write-Check -Name "Health endpoint" -Ok $ok -Details "(status=$($health.status))"
    if (-not $ok) { $failed = $true }
} catch {
    Write-Check -Name "Health endpoint" -Ok $false -Details $_.Exception.Message
    $failed = $true
}

if ($Login -and $Password) {
    try {
        $loginRes = Invoke-JsonRequest `
            -Method "POST" `
            -Url "$base/auth/login" `
            -Body @{ login = $Login; password = $Password }

        $token = [string]($loginRes.access_token)
        $ok = -not [string]::IsNullOrWhiteSpace($token)
        Write-Check -Name "Login" -Ok $ok
        if (-not $ok) { $failed = $true }
    } catch {
        Write-Check -Name "Login" -Ok $false -Details $_.Exception.Message
        $failed = $true
    }

    if ($token) {
        $headers = @{ Authorization = "Bearer $token" }

        try {
            $me = Invoke-JsonRequest -Method "GET" -Url "$base/auth/me" -Headers $headers
            $ok = ($null -ne $me.user_id)
            Write-Check -Name "Auth me" -Ok $ok -Details "(user_id=$($me.user_id))"
            if (-not $ok) { $failed = $true }
        } catch {
            Write-Check -Name "Auth me" -Ok $false -Details $_.Exception.Message
            $failed = $true
        }

        try {
            $tasks = Invoke-JsonRequest -Method "GET" -Url "$base/tasks?limit=5" -Headers $headers
            $items = @()
            if ($null -ne $tasks.items) { $items = @($tasks.items) }
            Write-Check -Name "Tasks list" -Ok $true -Details "(count=$($items.Count))"
        } catch {
            Write-Check -Name "Tasks list" -Ok $false -Details $_.Exception.Message
            $failed = $true
        }

        try {
            $periods = Invoke-JsonRequest -Method "GET" -Url "$base/periods" -Headers $headers
            $count = @($periods).Count
            Write-Check -Name "Privileged periods access" -Ok $true -Details "(count=$count)"
        } catch {
            Write-Check -Name "Privileged periods access" -Ok $false -Details $_.Exception.Message
            $failed = $true
        }
    }
} else {
    Write-Host "[INFO] Login/password not provided. Checked only public health endpoint."
}

if ($failed) {
    exit 1
}

exit 0
