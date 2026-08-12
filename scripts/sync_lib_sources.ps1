param(
    [string[]]$Names = @(),
    [switch]$Refresh
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$libsRoot = Join-Path $repoRoot "libs"
$sourceFile = Join-Path $libsRoot "sources.json"
$extractScript = Join-Path $PSScriptRoot "extract_source_archive.py"
$sources = Get-Content -LiteralPath $sourceFile -Raw | ConvertFrom-Json

function Get-GitHubRepository {
    param([string]$Url)

    $normalized = $Url -replace '\.git$', ''
    $match = [regex]::Match($normalized, 'github\.com[/:]([^/]+)/([^/]+)$')
    if (-not $match.Success) {
        throw "Only GitHub source URLs are supported: $Url"
    }
    return [PSCustomObject]@{
        owner = $match.Groups[1].Value
        repository = $match.Groups[2].Value
    }
}

function Invoke-CurlDownload {
    param(
        [string]$Url,
        [string]$Output
    )

    & curl.exe --fail --location --retry 3 --connect-timeout 20 --silent --show-error --output $Output $Url
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to download $Url (curl exit code $LASTEXITCODE)"
    }
}

function Get-SubmoduleDefinitions {
    param([string]$GitModulesPath)

    $definitions = @()
    $current = $null
    foreach ($line in Get-Content -LiteralPath $GitModulesPath) {
        $section = [regex]::Match($line, '^\s*\[submodule\s+"([^"]+)"\]\s*$')
        if ($section.Success) {
            if ($null -ne $current) {
                $definitions += $current
            }
            $current = [ordered]@{ name = $section.Groups[1].Value; path = ""; url = "" }
            continue
        }
        if ($null -eq $current) {
            continue
        }
        $property = [regex]::Match($line, '^\s*(path|url)\s*=\s*(.+?)\s*$')
        if ($property.Success) {
            $current[$property.Groups[1].Value] = $property.Groups[2].Value
        }
    }
    if ($null -ne $current) {
        $definitions += $current
    }
    return $definitions
}

function Expand-GitHubSource {
    param(
        [string]$Url,
        [string]$Commit,
        [string]$Destination,
        [string]$TempRoot
    )

    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $archive = Join-Path $TempRoot ("archive-" + [guid]::NewGuid().ToString("N") + ".tar.gz")
    $repository = $null
    $stripComponents = 1
    if ($Url -match 'github\.com[/:]') {
        $repository = Get-GitHubRepository $Url
        $archiveUrl = "https://codeload.github.com/$($repository.owner)/$($repository.repository)/tar.gz/$Commit"
    }
    elseif ($Url.TrimEnd('/') -eq 'https://chromium.googlesource.com/webm/libwebm') {
        # Gitiles may be unavailable on restricted networks; the official GitHub
        # mirror contains the same commit IDs.
        $repository = Get-GitHubRepository 'https://github.com/webmproject/libwebm'
        $archiveUrl = "https://codeload.github.com/webmproject/libwebm/tar.gz/$Commit"
    }
    else {
        throw "Unsupported source URL: $Url"
    }
    Invoke-CurlDownload $archiveUrl $archive
    & python $extractScript $archive $Destination --strip-components $stripComponents
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to extract $archiveUrl (extractor exit code $LASTEXITCODE)"
    }

    $gitModules = Join-Path $Destination ".gitmodules"
    if (-not (Test-Path -LiteralPath $gitModules)) {
        return
    }

    if ($null -eq $repository) {
        throw "Submodules are not yet supported for non-GitHub source: $Url"
    }

    $treeFile = Join-Path $TempRoot ("tree-" + [guid]::NewGuid().ToString("N") + ".json")
    $treeUrl = "https://api.github.com/repos/$($repository.owner)/$($repository.repository)/git/trees/$Commit`?recursive=1"
    Invoke-CurlDownload $treeUrl $treeFile
    $tree = (Get-Content -LiteralPath $treeFile -Raw | ConvertFrom-Json).tree

    foreach ($submodule in Get-SubmoduleDefinitions $gitModules) {
        if (-not $submodule.path -or -not $submodule.url) {
            throw "Invalid submodule entry '$($submodule.name)' in $gitModules"
        }
        $gitLink = $tree | Where-Object { $_.path -eq $submodule.path -and $_.type -eq "commit" } | Select-Object -First 1
        if ($null -eq $gitLink) {
            Write-Host "Skipping inactive submodule entry '$($submodule.path)'"
            continue
        }
        $submoduleDestination = Join-Path $Destination $submodule.path
        Expand-GitHubSource $submodule.url $gitLink.sha $submoduleDestination $TempRoot
    }
}

function Expand-GitHubSparseSource {
    param(
        [string]$Url,
        [string]$Commit,
        [object[]]$Includes,
        [string]$Destination,
        [string]$TempRoot
    )

    $repository = Get-GitHubRepository $Url
    $treeFile = Join-Path $TempRoot ("tree-" + [guid]::NewGuid().ToString("N") + ".json")
    $treeUrl = "https://api.github.com/repos/$($repository.owner)/$($repository.repository)/git/trees/$Commit`?recursive=1"
    Invoke-CurlDownload $treeUrl $treeFile
    $tree = (Get-Content -LiteralPath $treeFile -Raw | ConvertFrom-Json).tree

    $files = $tree | Where-Object {
        if ($_.type -ne "blob") {
            return $false
        }
        foreach ($include in $Includes) {
            if ($_.path -eq $include -or $_.path.StartsWith("$include/", [System.StringComparison]::Ordinal)) {
                return $true
            }
        }
        return $false
    }

    foreach ($file in $files) {
        $relativePath = $file.path -replace '/', [System.IO.Path]::DirectorySeparatorChar
        $output = Join-Path $Destination $relativePath
        $parent = Split-Path -Parent $output
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
        $segments = $file.path.Split('/') | ForEach-Object { [uri]::EscapeDataString($_) }
        $rawPath = $segments -join '/'
        $rawUrl = "https://raw.githubusercontent.com/$($repository.owner)/$($repository.repository)/$Commit/$rawPath"
        Invoke-CurlDownload $rawUrl $output
    }
}

function Apply-SourceReplacements {
    param(
        [object[]]$Replacements,
        [string]$SourceRoot
    )

    foreach ($replacement in $Replacements) {
        $file = Join-Path $SourceRoot ($replacement.file -replace '/', [System.IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $file)) {
            throw "Replacement target does not exist: $file"
        }
        $content = [System.IO.File]::ReadAllText($file)
        if (-not $content.Contains($replacement.from)) {
            if ($content.Contains($replacement.to)) {
                continue
            }
            throw "Replacement source text was not found in $file"
        }
        $content = $content.Replace($replacement.from, $replacement.to)
        $utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($file, $content, $utf8WithoutBom)
    }
}

if ($Names.Count -gt 0) {
    $sources = @($sources | Where-Object { $Names -contains $_.name })
}

foreach ($source in $sources) {
    $destination = Join-Path $libsRoot $source.name
    $marker = Join-Path $destination ".codedesk-source.json"

    if ((Test-Path -LiteralPath $marker) -and -not $Refresh) {
        $current = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
        if ($current.url -eq $source.url -and $current.commit -eq $source.commit) {
            Write-Host "[$($source.name)] already at $($source.commit)"
            continue
        }
    }

    if ((Test-Path -LiteralPath $destination) -and -not $Refresh) {
        throw "Destination already exists without the expected source marker: $destination"
    }

    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("codedesk-source-" + [guid]::NewGuid().ToString("N"))
    $stagedRoot = Join-Path $tempRoot "staged"
    New-Item -ItemType Directory -Path $stagedRoot -Force | Out-Null

    try {
        Write-Host "[$($source.name)] fetching $($source.commit)"
        if ($null -ne $source.include -and $source.include.Count -gt 0) {
            Expand-GitHubSparseSource $source.url $source.commit $source.include $stagedRoot $tempRoot
        }
        else {
            Expand-GitHubSource $source.url $source.commit $stagedRoot $tempRoot
        }
        if ($null -ne $source.replacements -and $source.replacements.Count -gt 0) {
            Apply-SourceReplacements $source.replacements $stagedRoot
        }

        [PSCustomObject]@{
            url = $source.url
            commit = $source.commit
        } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $stagedRoot ".codedesk-source.json") -Encoding ascii

        if (Test-Path -LiteralPath $destination) {
            $resolvedDestination = [System.IO.Path]::GetFullPath($destination)
            $resolvedLibsRoot = [System.IO.Path]::GetFullPath($libsRoot) + [System.IO.Path]::DirectorySeparatorChar
            if (-not $resolvedDestination.StartsWith($resolvedLibsRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "Refusing to replace a directory outside libs: $resolvedDestination"
            }
            Remove-Item -LiteralPath $resolvedDestination -Recurse -Force
        }
        Move-Item -LiteralPath $stagedRoot -Destination $destination
        Write-Host "[$($source.name)] imported"
    }
    finally {
        $resolvedTempRoot = [System.IO.Path]::GetFullPath($tempRoot)
        $systemTempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
        if ($resolvedTempRoot.StartsWith($systemTempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and
            (Test-Path -LiteralPath $resolvedTempRoot)) {
            Remove-Item -LiteralPath $resolvedTempRoot -Recurse -Force
        }
    }
}
