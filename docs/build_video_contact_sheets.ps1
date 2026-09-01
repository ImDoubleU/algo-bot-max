param(
    [string]$SlideRoot = "",
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($SlideRoot)) {
    $SlideRoot = Join-Path $Root "output\video-series\slides"
}
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $Root "output\video-series\contact-sheets"
}

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

$columns = 4
$thumbWidth = 384
$thumbHeight = 216
$labelHeight = 28
$margin = 12
$font = New-Object System.Drawing.Font("Arial", 11, [System.Drawing.FontStyle]::Bold)
$brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(35, 28, 51))
$background = [System.Drawing.Color]::FromArgb(242, 241, 247)

try {
    foreach ($directory in Get-ChildItem -LiteralPath $SlideRoot -Directory | Sort-Object Name) {
        $images = @(
            Get-ChildItem -LiteralPath $directory.FullName -File |
                Where-Object { $_.Extension -ieq ".png" } |
                Sort-Object { [int]([regex]::Match($_.BaseName, "\d+").Value) }
        )
        if ($images.Count -eq 0) {
            continue
        }

        $rows = [Math]::Ceiling($images.Count / $columns)
        $sheetWidth = $margin + $columns * ($thumbWidth + $margin)
        $sheetHeight = $margin + $rows * ($thumbHeight + $labelHeight + $margin)
        $bitmap = New-Object System.Drawing.Bitmap($sheetWidth, $sheetHeight)
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        try {
            $graphics.Clear($background)
            $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
            $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit

            for ($index = 0; $index -lt $images.Count; $index++) {
                $column = $index % $columns
                $row = [Math]::Floor($index / $columns)
                $x = $margin + $column * ($thumbWidth + $margin)
                $y = $margin + $row * ($thumbHeight + $labelHeight + $margin)
                $image = [System.Drawing.Image]::FromFile($images[$index].FullName)
                try {
                    $graphics.DrawImage($image, $x, $y, $thumbWidth, $thumbHeight)
                }
                finally {
                    $image.Dispose()
                }
                $graphics.DrawString("$($directory.Name) - slide $($index + 1)", $font, $brush, $x, $y + $thumbHeight + 4)
            }

            $target = Join-Path $OutputDirectory "$($directory.Name).png"
            $bitmap.Save($target, [System.Drawing.Imaging.ImageFormat]::Png)
            Write-Host "$($directory.Name): $($images.Count) slides -> $target"
        }
        finally {
            $graphics.Dispose()
            $bitmap.Dispose()
        }
    }
}
finally {
    $font.Dispose()
    $brush.Dispose()
}
