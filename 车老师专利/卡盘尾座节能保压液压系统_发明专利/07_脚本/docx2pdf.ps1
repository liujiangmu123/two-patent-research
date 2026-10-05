# Convert *.docx in -Dir to PDF with Word COM (fields updated), print page counts. ASCII only (PS 5.1 safe).
param([Parameter(Mandatory = $true)][string]$Dir, [string[]]$Only = @())
$ErrorActionPreference = "Stop"
$w = New-Object -ComObject Word.Application
$w.Visible = $false
$w.DisplayAlerts = 0
try {
  Get-ChildItem -LiteralPath $Dir -Filter *.docx | Where-Object { $_.Name -notlike '~$*' -and ($Only.Count -eq 0 -or $Only -contains $_.BaseName) } | ForEach-Object {
    $d = $w.Documents.Open($_.FullName, $false, $true)
    $d.Repaginate()
    foreach ($s in $d.Sections) { foreach ($f in $s.Footers) { $f.Range.Fields.Update() | Out-Null } }
    $pdf = [IO.Path]::ChangeExtension($_.FullName, ".pdf")
    $d.ExportAsFixedFormat($pdf, 17)
    $pages = $d.ComputeStatistics(2)
    $secs = @()
    foreach ($s in $d.Sections) { $secs += $s.Range.Information(3) }
    "{0}: pages={1}; section end pages={2}" -f $_.Name, $pages, ($secs -join ",")
    $d.Close($false)
  }
} finally { $w.Quit() }
