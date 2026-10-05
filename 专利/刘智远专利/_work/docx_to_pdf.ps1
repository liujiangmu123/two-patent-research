# Render a DOCX to PDF with Word (invisible) for visual verification.
param([Parameter(Mandatory = $true)][string]$Docx, [Parameter(Mandatory = $true)][string]$Pdf)
$ErrorActionPreference = "Stop"
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($Docx, $false, $true, $false)
    $doc.ExportAsFixedFormat($Pdf, 17)   # 17 = wdExportFormatPDF
    Write-Output ("pages: " + $doc.ComputeStatistics(2))
    $doc.Close($false)
}
finally {
    $word.Quit()
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
}
