param(
    [string[]]$Only = @(),
    [string]$PiperModel = "",
    [switch]$SkipSlides,
    [switch]$SkipVideo,
    [switch]$SyntheticVoice
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ManifestPath = Join-Path $Root "docs\video_series_manifest.json"
$Python = Join-Path $Root "max_bot_venv\Scripts\python.exe"
$PiperScript = Join-Path $Root "docs\build_piper_audio.py"
$MasterScript = Join-Path $Root "docs\build_video_master.py"
$Ffmpeg = Join-Path $Root "output\.audit-tools\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
$OutputDir = Join-Path $Root "output\video-series"
$SlideRoot = Join-Path $OutputDir "slides"
$AudioRoot = Join-Path $OutputDir "audio"
$PdfRoot = Join-Path $Root "output\pdf\video-series"
$ExportManifestPath = Join-Path $OutputDir "export-manifest.json"

if ([string]::IsNullOrWhiteSpace($PiperModel)) {
    $PiperModel = Join-Path $Root "output\tts-models\ru_RU-dmitri-medium.onnx"
}

foreach ($required in @($ManifestPath, $Python, $MasterScript, $Ffmpeg)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required file was not found: $required"
    }
}
if ($SyntheticVoice) {
    foreach ($required in @($PiperScript, $PiperModel)) {
        if (-not (Test-Path -LiteralPath $required)) {
            throw "Required synthetic voice file was not found: $required"
        }
    }
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$videos = @($manifest.videos | ForEach-Object { $_ })
if ($Only.Count -gt 0) {
    $requested = @(
        $Only |
            ForEach-Object { $_ -split ',' } |
            ForEach-Object { $_.Trim().ToLowerInvariant() } |
            Where-Object { $_ }
    )
    $videos = @($videos | Where-Object { $requested -contains ([string]$_.id).ToLowerInvariant() })
    $missing = @($requested | Where-Object { $_ -notin @($videos | ForEach-Object { ([string]$_.id).ToLowerInvariant() }) })
    if ($missing.Count -gt 0) {
        throw "Unknown video ids: $($missing -join ', ')"
    }
}
if ($videos.Count -eq 0) {
    throw "No videos were selected from the manifest"
}

New-Item -ItemType Directory -Force -Path $OutputDir, $SlideRoot, $AudioRoot, $PdfRoot | Out-Null

function Release-ComObject {
    param([object]$Value)
    if ($null -ne $Value -and [System.Runtime.InteropServices.Marshal]::IsComObject($Value)) {
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($Value)
    }
}

function Resolve-ProjectPath {
    param([string]$RelativePath)
    return Join-Path $Root $RelativePath
}

function Export-PresentationSlides {
    param(
        [object]$PowerPoint,
        [string]$Source,
        [string]$TargetDirectory
    )

    New-Item -ItemType Directory -Force -Path $TargetDirectory | Out-Null
    Get-ChildItem -LiteralPath $TargetDirectory -Filter "*.PNG" -File -ErrorAction SilentlyContinue | Remove-Item -Force
    $presentation = $null
    try {
        $presentation = $PowerPoint.Presentations.Open($Source, $true, $false, $false)
        $presentation.Export($TargetDirectory, "PNG", 1920, 1080)
    }
    finally {
        if ($null -ne $presentation) {
            $presentation.Close()
            Release-ComObject $presentation
        }
    }
}

function Export-PresentationPdf {
    param(
        [object]$PowerPoint,
        [string]$Source,
        [string]$Target
    )

    $presentation = $null
    try {
        $presentation = $PowerPoint.Presentations.Open($Source, $true, $false, $false)
        $presentation.SaveAs($Target, 32)
    }
    finally {
        if ($null -ne $presentation) {
            $presentation.Close()
            Release-ComObject $presentation
        }
    }
}

function Build-PiperNarration {
    param(
        [string]$NarrationPath,
        [string]$TargetDirectory,
        [string]$TargetManifest
    )

    New-Item -ItemType Directory -Force -Path $TargetDirectory | Out-Null
    & $Python $PiperScript `
        --narration $NarrationPath `
        --model $PiperModel `
        --output-dir $TargetDirectory `
        --manifest $TargetManifest | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0) {
        throw "Piper exited with code $LASTEXITCODE"
    }
    $document = Get-Content -LiteralPath $TargetManifest -Raw -Encoding UTF8 | ConvertFrom-Json
    return @($document | ForEach-Object { $_ })
}

function Build-VideoMaster {
    param(
        [string]$VideoId,
        [bool]$UseSyntheticVoice
    )

    $arguments = @(
        $MasterScript,
        "--manifest", $ManifestPath,
        "--video-id", $VideoId,
        "--ffmpeg", $Ffmpeg
    )
    if (-not $UseSyntheticVoice) {
        $arguments += "--silent"
    }
    & $Python @arguments | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0) {
        throw "Video master builder exited with code $LASTEXITCODE"
    }
}

$results = @()
$powerPoint = New-Object -ComObject PowerPoint.Application
try {
    foreach ($entry in $videos) {
        $id = [string]$entry.id
        $source = Resolve-ProjectPath ([string]$entry.presentation)
        $narration = Resolve-ProjectPath ([string]$entry.narration)
        $targetVideo = Resolve-ProjectPath ([string]$entry.video)
        $targetPdf = Resolve-ProjectPath ([string]$entry.pdf)
        $slideDirectory = Join-Path $SlideRoot $id
        $audioDirectory = Join-Path $AudioRoot $id
        $audioManifest = Join-Path $audioDirectory "piper-manifest.json"

        foreach ($required in @($source, $narration)) {
            if (-not (Test-Path -LiteralPath $required)) {
                throw "Source for '$id' was not found: $required"
            }
        }

        Write-Host ""
        Write-Host ("[{0:D2}] {1}" -f [int]$entry.order, [string]$entry.title)
        if (-not $SkipSlides) {
            Write-Host "Exporting review PNG files..."
            Export-PresentationSlides -PowerPoint $powerPoint -Source $source -TargetDirectory $slideDirectory
        }
        Write-Host "Exporting PDF..."
        Export-PresentationPdf -PowerPoint $powerPoint -Source $source -Target $targetPdf

        $timelineSeconds = [double]$entry.estimated_seconds
        $audioSeconds = 0.0
        if (-not $SkipVideo) {
            if ($SyntheticVoice) {
                Write-Host "Building optional synthetic narration..."
                $audioTracks = @(Build-PiperNarration -NarrationPath $narration -TargetDirectory $audioDirectory -TargetManifest $audioManifest)
                $audioSeconds = ($audioTracks | Measure-Object -Property AudioSeconds -Sum).Sum
            }
            else {
                Write-Host "Building silent master for human voiceover..."
            }
            Write-Host "Building 1080p MP4, subtitles and chapters..."
            Build-VideoMaster -VideoId $id -UseSyntheticVoice ([bool]$SyntheticVoice)
        }
        elseif ($SyntheticVoice -and (Test-Path -LiteralPath $audioManifest)) {
            $existingTracks = Get-Content -LiteralPath $audioManifest -Raw -Encoding UTF8 | ConvertFrom-Json
            $audioSeconds = (@($existingTracks | ForEach-Object { $_ }) | Measure-Object -Property AudioSeconds -Sum).Sum
        }

        $results += [pscustomobject]@{
            id = $id
            title = [string]$entry.title
            slides = [int]$entry.slides
            duration_seconds = [Math]::Round($timelineSeconds, 3)
            audio_seconds = [Math]::Round([double]$audioSeconds, 3)
            audio_mode = if ($SyntheticVoice) { "synthetic" } else { "silent_for_human_voiceover" }
            video = [string]$entry.video
            pdf = [string]$entry.pdf
            video_bytes = if (Test-Path -LiteralPath $targetVideo) { (Get-Item -LiteralPath $targetVideo).Length } else { 0 }
            subtitles_srt = [string]$entry.subtitles_srt
            subtitles_vtt = [string]$entry.subtitles_vtt
            chapters = [string]$entry.chapters
        }
    }
}
finally {
    if ($null -ne $powerPoint) {
        $powerPoint.Quit()
        Release-ComObject $powerPoint
        [GC]::Collect()
        [GC]::WaitForPendingFinalizers()
    }
}

@{
    series = [string]$manifest.series
    voice = if ($SyntheticVoice) { "synthetic" } else { "manual" }
    videos = $results
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ExportManifestPath -Encoding UTF8

Write-Host ""
Write-Host "Done:"
foreach ($result in $results) {
    Write-Host ("  {0}: {1}" -f $result.id, (Resolve-ProjectPath $result.video))
}
Write-Host "  $ExportManifestPath"
