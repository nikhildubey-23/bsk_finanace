# Test if WIA COM is available at all
powershell -ExecutionPolicy Bypass -Command "
try {
    $dm = New-Object -ComObject WIA.DeviceManager
    Write-Output 'WIA DeviceManager: SUCCESS'
    Write-Output ('Devices: ' + $dm.DeviceInfos.Count)
} catch {
    Write-Output ('WIA Error: ' + $_.Exception.Message)
}

# Try Scripting.FileSystemObject as a test
try {
    $fs = New-Object -ComObject Scripting.FileSystemObject
    Write-Output 'COM Test: SUCCESS'
} catch {
    Write-Output ('COM Test Error: ' + $_.Exception.Message)
}
"
