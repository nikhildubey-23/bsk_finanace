$ErrorActionPreference = "Stop"

$scannerId = "{6BDD1FC6-810F-11D0-BEC7-08002BE2092F}\0000"
$outputPath = "C:\Users\Dell\Desktop\backoffice\bsk_finanace\uploads\temp\test_scan.jpg"

try {
    Add-Type -AssemblyName System.Drawing
    
    $deviceManager = New-Object -ComObject WIA.DeviceManager
    $device = $deviceManager.DeviceInfos | Where-Object { $_.DeviceID -eq $scannerId }
    
    if (-not $device) {
        Write-Error "Scanner not found"
        exit 1
    }
    
    Write-Output "Connecting to scanner..."
    $wiaDevice = $device.Connect()
    
    Write-Output ("Items: " + $wiaDevice.Items.Count)
    
    $item = $wiaDevice.Items[1]
    
    Write-Output "Transferring..."
    $image = $item.Transfer("Image.JPEG")
    
    Write-Output "Saving..."
    $image.SaveFile($outputPath)
    
    Write-Output "SUCCESS"
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
