param(
    [string]$VoiceName = "Microsoft Irina Desktop - Russian",
    [ValidateSet("Piper", "Sapi")]
    [string]$TtsProvider = "Piper",
    [string]$PiperModel = "",
    [switch]$SkipVideo,
    [switch]$SyntheticVoice
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$GuidePptx = Join-Path $Root "docs\Algo_MAX_Руководство_по_ролям.pptx"
$ProductPptx = Join-Path $Root "docs\Algo_MAX_Презентация_продукта.pptx"
$NarrationJson = Join-Path $Root "docs\product_video_narration.json"
$PiperScript = Join-Path $Root "docs\build_piper_audio.py"
$Python = Join-Path $Root "max_bot_venv\Scripts\python.exe"
$PdfDir = Join-Path $Root "output\pdf"
$VideoDir = Join-Path $Root "output\video"
$AudioDir = Join-Path $VideoDir "audio"
$PiperManifest = Join-Path $AudioDir "piper-manifest.json"
$SlideDir = Join-Path $Root "output\presentation-slides"
$GuideSlideDir = Join-Path $Root "output\guide-slides"
$GuidePdf = Join-Path $PdfDir "Algo_MAX_Полное_руководство.pdf"
$ProductPdf = Join-Path $PdfDir "Algo_MAX_Презентация_продукта.pdf"
$NarratedPptx = Join-Path $VideoDir "Algo_MAX_Презентация_с_озвучкой.pptx"
$VideoPath = Join-Path $VideoDir "Algo_MAX_Обзор_продукта.mp4"

if ([string]::IsNullOrWhiteSpace($PiperModel)) {
    $PiperModel = Join-Path $Root "output\tts-models\ru_RU-dmitri-medium.onnx"
}

foreach ($required in @($GuidePptx, $ProductPptx, $NarrationJson)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Не найден обязательный файл: $required"
    }
}

New-Item -ItemType Directory -Force -Path $PdfDir, $VideoDir, $AudioDir, $SlideDir, $GuideSlideDir | Out-Null

function Release-ComObject {
    param([object]$Value)
    if ($null -ne $Value -and [System.Runtime.InteropServices.Marshal]::IsComObject($Value)) {
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($Value)
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
        # PowerPoint's COM dispatcher does not expose optional ExportAsFixedFormat
        # arguments consistently in Windows PowerShell 5.1. SaveAs with the PDF
        # format constant is stable across the supported Office versions.
        $presentation.SaveAs($Target, 32)
    }
    finally {
        if ($null -ne $presentation) {
            $presentation.Close()
            Release-ComObject $presentation
        }
    }
}

function Export-PresentationSlides {
    param(
        [object]$PowerPoint,
        [string]$Source,
        [string]$TargetDirectory
    )

    Get-ChildItem -LiteralPath $TargetDirectory -Filter "*.PNG" -ErrorAction SilentlyContinue | Remove-Item -Force
    $presentation = $null
    try {
        $presentation = $PowerPoint.Presentations.Open($Source, $true, $false, $false)
        $presentation.Export($TargetDirectory, "PNG", 1600, 900)
    }
    finally {
        if ($null -ne $presentation) {
            $presentation.Close()
            Release-ComObject $presentation
        }
    }
}

function Get-WavDurationSeconds {
    param([string]$Path)

    $stream = [System.IO.File]::OpenRead($Path)
    $reader = New-Object System.IO.BinaryReader($stream)
    try {
        $riff = -join $reader.ReadChars(4)
        [void]$reader.ReadUInt32()
        $wave = -join $reader.ReadChars(4)
        if ($riff -ne "RIFF" -or $wave -ne "WAVE") {
            throw "Неподдерживаемый WAV: $Path"
        }

        [double]$byteRate = 0
        [double]$dataSize = 0
        while ($stream.Position + 8 -le $stream.Length) {
            $chunkId = -join $reader.ReadChars(4)
            [uint32]$chunkSize = $reader.ReadUInt32()
            [long]$chunkStart = $stream.Position
            if ($chunkId -eq "fmt ") {
                [void]$reader.ReadUInt16()
                [void]$reader.ReadUInt16()
                [void]$reader.ReadUInt32()
                $byteRate = $reader.ReadUInt32()
            }
            elseif ($chunkId -eq "data") {
                $dataSize = $chunkSize
                break
            }
            $stream.Position = $chunkStart + $chunkSize + ($chunkSize % 2)
        }

        if ($byteRate -le 0 -or $dataSize -le 0) {
            throw "Не удалось определить длительность WAV: $Path"
        }
        return $dataSize / $byteRate
    }
    finally {
        $reader.Dispose()
        $stream.Dispose()
    }
}

function Build-SapiNarrationAudio {
    param(
        [object[]]$Narration,
        [string]$TargetDirectory,
        [string]$PreferredVoice
    )

    $voice = New-Object -ComObject SAPI.SpVoice
    try {
        $voiceToken = @($voice.GetVoices() | Where-Object { $_.GetDescription() -eq $PreferredVoice }) | Select-Object -First 1
        if ($null -eq $voiceToken) {
            $available = @($voice.GetVoices() | ForEach-Object { $_.GetDescription() }) -join ", "
            throw "Русский голос '$PreferredVoice' не найден. Доступны: $available"
        }
        $voice.Voice = $voiceToken
        $voice.Rate = 1
        $voice.Volume = 100

        $result = @()
        for ($index = 0; $index -lt $Narration.Count; $index++) {
            $number = $index + 1
            $audioPath = Join-Path $TargetDirectory ("slide-{0:D2}.wav" -f $number)
            $stream = New-Object -ComObject SAPI.SpFileStream
            try {
                $stream.Open($audioPath, 3, $false)
                $voice.AudioOutputStream = $stream
                [void]$voice.Speak([string]$Narration[$index].text)
                $stream.Close()
            }
            finally {
                Release-ComObject $stream
            }
            $duration = Get-WavDurationSeconds -Path $audioPath
            $result += [pscustomobject]@{
                Slide = $number
                Path = $audioPath
                Duration = [Math]::Ceiling($duration + 0.8)
            }
        }
        return $result
    }
    finally {
        Release-ComObject $voice
    }
}

function Build-PiperNarrationAudio {
    param(
        [string]$NarrationPath,
        [string]$ModelPath,
        [string]$TargetDirectory,
        [string]$ManifestPath
    )

    foreach ($required in @($Python, $PiperScript, $ModelPath)) {
        if (-not (Test-Path -LiteralPath $required)) {
            throw "Не найден обязательный файл для Piper: $required"
        }
    }

    & $Python $PiperScript `
        --narration $NarrationPath `
        --model $ModelPath `
        --output-dir $TargetDirectory `
        --manifest $ManifestPath | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0) {
        throw "Piper завершился с кодом $LASTEXITCODE"
    }

    $manifestDocument = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    return @($manifestDocument | ForEach-Object { $_ })
}

function Export-NarratedVideo {
    param(
        [object]$PowerPoint,
        [string]$Source,
        [string]$WorkingPresentation,
        [string]$TargetVideo,
        [object[]]$AudioTracks
    )

    Copy-Item -LiteralPath $Source -Destination $WorkingPresentation -Force
    if (Test-Path -LiteralPath $TargetVideo) {
        Remove-Item -LiteralPath $TargetVideo -Force
    }

    $presentation = $null
    try {
        $presentation = $PowerPoint.Presentations.Open($WorkingPresentation, $false, $false, $false)
        if ($presentation.Slides.Count -ne $AudioTracks.Count) {
            throw "Слайдов в презентации: $($presentation.Slides.Count), дорожек озвучки: $($AudioTracks.Count)"
        }

        foreach ($track in $AudioTracks) {
            $slide = $presentation.Slides.Item([int]$track.Slide)
            $media = $slide.Shapes.AddMediaObject2([string]$track.Path, $false, $true, -100, -100, 1, 1)
            $media.AnimationSettings.Animate = -1
            $media.AnimationSettings.PlaySettings.PlayOnEntry = -1
            $media.AnimationSettings.PlaySettings.HideWhileNotPlaying = -1
            $media.AnimationSettings.PlaySettings.StopAfterSlides = 1
            $slide.SlideShowTransition.AdvanceOnClick = 0
            $slide.SlideShowTransition.AdvanceOnTime = -1
            $slide.SlideShowTransition.AdvanceTime = [double]$track.Duration
            Release-ComObject $media
            Release-ComObject $slide
        }

        $presentation.Save()
        $presentation.CreateVideo($TargetVideo, $true, 5, 720, 24, 90)
        $deadline = (Get-Date).AddMinutes(40)
        do {
            Start-Sleep -Seconds 5
            $status = [int]$presentation.CreateVideoStatus
            Write-Host "Экспорт видео: статус $status"
            if ((Get-Date) -gt $deadline) {
                throw "Экспорт видео не завершился за 40 минут"
            }
        } while ($status -in @(1, 2))

        if ($status -ne 3 -or -not (Test-Path -LiteralPath $TargetVideo)) {
            throw "PowerPoint не создал видео, итоговый статус: $status"
        }
    }
    finally {
        if ($null -ne $presentation) {
            $presentation.Close()
            Release-ComObject $presentation
        }
    }
}

$powerPoint = New-Object -ComObject PowerPoint.Application
try {
    Write-Host "Экспорт подробного руководства в PDF и PNG..."
    Export-PresentationPdf -PowerPoint $powerPoint -Source $GuidePptx -Target $GuidePdf
    Export-PresentationSlides -PowerPoint $powerPoint -Source $GuidePptx -TargetDirectory $GuideSlideDir

    Write-Host "Экспорт краткой презентации в PDF и PNG..."
    Export-PresentationPdf -PowerPoint $powerPoint -Source $ProductPptx -Target $ProductPdf
    Export-PresentationSlides -PowerPoint $powerPoint -Source $ProductPptx -TargetDirectory $SlideDir

    if (-not $SkipVideo -and $SyntheticVoice) {
        # Windows PowerShell 5.1 may preserve the top-level JSON array as one
        # nested object inside @(...). Sending it through the pipeline expands
        # every slide entry reliably.
        $narrationDocument = Get-Content -LiteralPath $NarrationJson -Raw -Encoding UTF8 | ConvertFrom-Json
        $narration = @($narrationDocument | ForEach-Object { $_ })
        Write-Host "Слайдов озвучки: $($narration.Count)"
        Write-Host "Создание русской озвучки: $TtsProvider..."
        if ($TtsProvider -eq "Piper") {
            $audioTracks = @(
                Build-PiperNarrationAudio `
                    -NarrationPath $NarrationJson `
                    -ModelPath $PiperModel `
                    -TargetDirectory $AudioDir `
                    -ManifestPath $PiperManifest
            )
        }
        else {
            $audioTracks = @(Build-SapiNarrationAudio -Narration $narration -TargetDirectory $AudioDir -PreferredVoice $VoiceName)
        }
        Write-Host "Создание MP4..."
        Export-NarratedVideo -PowerPoint $powerPoint -Source $ProductPptx -WorkingPresentation $NarratedPptx -TargetVideo $VideoPath -AudioTracks $audioTracks
    }
}
finally {
    $powerPoint.Quit()
    Release-ComObject $powerPoint
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

Write-Host "Готово:"
Write-Host "  $GuidePdf"
Write-Host "  $ProductPdf"
if (-not $SkipVideo -and $SyntheticVoice) {
    Write-Host "  $VideoPath"
}
