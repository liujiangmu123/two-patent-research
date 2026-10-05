# Convert .docx files to PDF with Word COM (update TOC and fields first), print page counts.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File docx2pdf.ps1 -Dir <folder> [-Only name1,name2] [-Files a.docx,b.docx]
# ASCII only (PowerShell 5.1 safe). Runs hidden; no dialogs.
param([string]$Dir = "", [string[]]$Only = @(), [string[]]$Files = @())
$ErrorActionPreference = "Stop"
$items = @()
if ($Files.Count -gt 0) { $items = $Files | ForEach-Object { Get-Item -LiteralPath $_ } }
elseif ($Dir -ne "") { $items = Get-ChildItem -LiteralPath $Dir -Filter *.docx | Where-Object { $_.Name -notlike '~$*' -and ($Only.Count -eq 0 -or $Only -contains $_.BaseName) } }
if ($items.Count -eq 0) { "no docx"; exit 0 }
$w = New-Object -ComObject Word.Application
$w.Visible = $false
$w.DisplayAlerts = 0
try {
  foreach ($it in $items) {
    $d = $w.Documents.Open($it.FullName, $false, $false)
    try {
      foreach ($t in $d.TablesOfContents) { $t.Update() | Out-Null }
      $d.Fields.Update() | Out-Null
      $d.Repaginate()
      foreach ($s in $d.Sections) { foreach ($f in $s.Footers) { $f.Range.Fields.Update() | Out-Null } }
      if ($d.TablesOfContents.Count -gt 0) { $d.Save() }
      $pdf = [IO.Path]::ChangeExtension($it.FullName, ".pdf")
      $d.ExportAsFixedFormat($pdf, 17)
      $pages = $d.ComputeStatistics(2)
      "{0}: pages={1}" -f $it.Name, $pages
    } finally { $d.Close($false) }
  }
} finally { $w.Quit() }
