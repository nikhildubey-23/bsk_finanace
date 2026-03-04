$ErrorActionPreference = "Stop"

$scannerId = "{6BDD1FC6-810F-11D0-BEC7-08002BE2092F}\0000"
$outputPath = "C:\Users\Dell\Desktop\backoffice\bsk_finanace\uploads\temp\test_scan.jpg"

try {
    Add-Type -AssemblyName System.Drawing
    
    # Use WIA Common Dialog instead
    $dialog = New-Object -ComObject WIA.CommonDialog
    
    Write-Output "Showing scan dialog..."
    # Show the WIA scan dialog - this is more reliable
    $image = $dialog.ShowAcquireImage(
        [int][WIA.WiaDeviceType]::ScannerDeviceType,
        [int][WIA.WiaImageIntent]::GrayscaleIntent,
        [int][WIA.WiaImageFormat]::JPEG,
        $null,
        $true,
        $false,
        $false
    )
    
    if ($image) {
        Write-Output "Saving..."
        $image.SaveFile($outputPath)
        Write-Output "SUCCESS"
    } else {
        Write-Output "Cancelled"
    }
    
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
