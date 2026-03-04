$ErrorActionPreference = "Stop"

$scannerId = "{6BDD1FC6-810F-11D0-BEC7-08002BE2092F}\0000"
$outputPath = "C:\Users\Dell\Desktop\backoffice\bsk_finanace\uploads\temp\test_scan.jpg"

try {
    # Load WIA interop
    Add-Type -AssemblyName System.Drawing
    
    # Try direct image acquisition without WIA.CommonDialog
    $dialog = New-Object -ComObject WIA.CommonDialog
    
    Write-Output "Showing scan dialog..."
    # Try with default parameters
    $image = $dialog.ShowAcquireImage()
    
    if ($image) {
        Write-Output "Saving..."
        $image.SaveFile($outputPath)
        Write-Output "SUCCESS"
    } else {
        Write-Output "Cancelled or no image"
    }
    
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
