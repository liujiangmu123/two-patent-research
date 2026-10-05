# Markdown reports -> docx (pandoc) -> fonts/tables/margins fixed by Word COM -> pdf. ASCII-only script (PS 5.1).
param([Parameter(Mandatory = $true)][string[]]$Md)
$ErrorActionPreference = "Stop"
$docs = @()
foreach ($m0 in $Md) {
  $m = [IO.Path]::GetFullPath($m0)          # normalize "/" to "\" (Word COM may open "/" paths read-only)
  $dir = Split-Path -Parent $m
  $docx = [IO.Path]::ChangeExtension($m, ".docx")
  pandoc $m -f markdown -t docx -o $docx --resource-path="$dir"
  if ($LASTEXITCODE -ne 0) { throw "pandoc failed: $m" }
  $docs += $docx
}
$w = New-Object -ComObject Word.Application
$w.Visible = $false
$w.DisplayAlerts = 0
$song = [string][char]0x5B8B + [char]0x4F53          # SimSun
$hei = [string][char]0x9ED1 + [char]0x4F53           # SimHei
try {
  foreach ($p in $docs) {
    $d = $w.Documents.Open($p)
    foreach ($s in $d.Sections) {
      $s.PageSetup.TopMargin = 72; $s.PageSetup.BottomMargin = 60
      $s.PageSetup.LeftMargin = 64; $s.PageSetup.RightMargin = 64
      $s.PageSetup.PaperSize = 7
    }
    foreach ($name in @(-1, -155, -156, -157)) {          # Normal, Body Text? use built-in ids below
    }
    $ids = @{ -1 = @($song, 10.5, $false); -2 = @($hei, 16, $true); -3 = @($hei, 13, $true); -4 = @($hei, 11.5, $true); -63 = @($hei, 18, $true) }
    foreach ($k in $ids.Keys) {
      try {
        $st = $d.Styles.Item($k)
        $st.Font.NameFarEast = $ids[$k][0]
        $st.Font.Name = "Times New Roman"
        $st.Font.Size = $ids[$k][1]
        $st.Font.Bold = $ids[$k][2]
        $st.Font.Color = 0
      } catch {}
    }
    foreach ($nm in @("Body Text", "First Paragraph", "Compact", "Block Text")) {
      try { $st = $d.Styles.Item($nm); $st.Font.NameFarEast = $song; $st.Font.Name = "Times New Roman"; $st.Font.Size = 10.5; $st.ParagraphFormat.SpaceAfter = 4 } catch {}
    }
    try { $st = $d.Styles.Item("Source Text"); $st.Font.Size = 9 } catch {}
    $d.Content.Font.NameFarEast = $song
    foreach ($h in @(-2, -3, -4, -63)) {
      try {
        $rng = $d.Content
        $f = $rng.Find
        $f.ClearFormatting()
        $f.Style = $d.Styles.Item($h)
        $f.Text = ""
        $f.Format = $true
        while ($f.Execute()) { $rng.Font.NameFarEast = $hei; $rng.Collapse(0) }
      } catch {}
    }
    foreach ($t in $d.Tables) {
      $t.Borders.Enable = $true
      $t.Range.Font.Size = 9
      $t.Range.ParagraphFormat.SpaceAfter = 0
      $t.Rows.Item(1).Range.Font.Bold = $true
      $t.Rows.Item(1).Shading.BackgroundPatternColor = 15132390
      $t.PreferredWidthType = 2
      $t.PreferredWidth = 100
    }
    foreach ($ils in $d.InlineShapes) {
      $maxw = 467
      if ($ils.Width -gt $maxw) { $r = $maxw / $ils.Width; $ils.Width = $maxw; $ils.Height = $ils.Height * $r }
    }
    $d.Save()
    $pdf = [IO.Path]::ChangeExtension($p, ".pdf")
    $d.ExportAsFixedFormat($pdf, 17)
    "{0}: pages={1}" -f (Split-Path -Leaf $p), $d.ComputeStatistics(2)
    $d.Close($false)
  }
} finally { $w.Quit() }
