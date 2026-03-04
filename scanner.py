"""
Scanner Module for InsureVault Pro
Uses Windows Image Acquisition (WIA) via the comtypes Python library
to directly communicate with scanner hardware without PowerShell.
"""
import os
import uuid
import platform
from datetime import datetime

try:
    import comtypes.client
    import comtypes
    COMTYPES_AVAILABLE = True
except ImportError:
    COMTYPES_AVAILABLE = False
    comtypes = None

def _init_com():
    """Initialize COM for the current thread"""
    if comtypes is not None:
        try:
            comtypes.CoInitialize()
        except Exception:
            pass

# --- WIA Constants ---
# These constants are used to interact with the WIA API.

# Device and Intent Types
WIA_DEVICE_TYPE_SCANNER = 1
WIA_INTENT_IMAGE_TYPE_COLOR = 1
WIA_INTENT_IMAGE_TYPE_GRAYSCALE = 2
WIA_INTENT_IMAGE_TYPE_TEXT = 4

# Image Formats (by GUID)
WIA_IMG_FORMAT_JPG = "{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}"
WIA_IMG_FORMAT_PNG = "{B96B3CAF-0728-11D3-9D7B-0000F81EF32E}"
WIA_IMG_FORMAT_BMP = "{B96B3CAB-0728-11D3-9D7B-0000F81EF32E}"

# Property IDs and Values for Document Feeder
WIA_PROPERTY_DOCUMENT_HANDLING_SELECT = 3088 
WIA_DOCUMENT_HANDLING_SELECT_FEEDER = 1
WIA_DOCUMENT_HANDLING_SELECT_FLATBED = 2

# Error Codes
WIA_ERROR_PAPER_EMPTY = -2145320957  # 0x80210003

def get_scanners():
    """
    Get list of available scanners using WIA and comtypes.
    Returns a list of scanner devices.
    """
    if platform.system() != 'Windows':
        return {"success": False, "error": "Scanner feature is only available on Windows", "scanners": []}
    if not COMTYPES_AVAILABLE:
        return {"success": False, "error": "comtypes library is not installed. Please run 'pip install comtypes'", "scanners": []}

    _init_com()
    
    try:
        device_manager = comtypes.client.CreateObject("WIA.DeviceManager")
        scanners = []
        for device_info in device_manager.DeviceInfos:
            if device_info.Type == WIA_DEVICE_TYPE_SCANNER:
                scanners.append({
                    "id": device_info.DeviceID,
                    "name": device_info.Properties("Name").Value
                })
        
        if not scanners:
            return {"success": False, "error": "No WIA-compatible scanners found.", "scanners": []}
        
        return {"success": True, "scanners": scanners}
    except Exception as e:
        return {"success": False, "error": f"Failed to get scanners: {str(e)}", "scanners": []}


def scan_document(scanner_id, output_format="jpg", output_folder="uploads/temp", multiscan=False, scan_mode="dialog"):
    """
    Scan one or more documents from a specified scanner using WIA.

    Args:
        scanner_id (str): The device ID of the scanner.
        output_format (str): The desired image format ('jpg', 'png', 'bmp').
        output_folder (str): The folder where scanned documents will be saved.
        multiscan (bool): If True, enables multi-page scanning from the ADF. 
                          If False, shows the standard WIA dialog for a single scan.
    
    Returns:
        dict: A dictionary containing the success status and a list of scanned files.
    """
    if platform.system() != 'Windows' or not COMTYPES_AVAILABLE:
        return {"success": False, "error": "Scanning is not supported on this system."}

    _init_com()

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    try:
        if multiscan and scan_mode == "flatbed":
            # --- Multi-page scan from Flatbed (manual, prompts for each page) ---
            scanned_files = []
            page_count = 1
            
            while True:
                dialog = comtypes.client.CreateObject("WIA.CommonDialog")
                image = dialog.ShowAcquireImage()
                
                if not image:
                    if page_count == 1:
                        return {"success": False, "error": "Scan cancelled by user."}
                    break  # User cancelled after first page - finish scanning
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"scan_{timestamp}_{uuid.uuid4().hex[:8]}_page_{page_count}.{output_format.lower()}"
                output_path = os.path.join(output_folder, filename)
                
                image.SaveFile(output_path)
                scanned_files.append({"filename": filename, "filepath": output_path})
                page_count += 1
            
            if not scanned_files:
                return {"success": False, "error": "No pages were scanned."}
            
            return {"success": True, "files": scanned_files}
        
        elif not multiscan:
            # --- Single-page scan using WIA Common Dialog ---
            dialog = comtypes.client.CreateObject("WIA.CommonDialog")
            image = dialog.ShowAcquireImage()
            
            if not image:
                return {"success": False, "error": "Scan cancelled by user."}

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"scan_{timestamp}_{uuid.uuid4().hex[:8]}.{output_format.lower()}"
            output_path = os.path.join(output_folder, filename)
            
            # Save the file and return the result
            image.SaveFile(output_path)
            return {"success": True, "files": [{"filename": filename, "filepath": output_path}]}

        else:
            # --- Multi-page scan from Automatic Document Feeder (ADF) ---
            device_manager = comtypes.client.CreateObject("WIA.DeviceManager")
            device = None
            for info in device_manager.DeviceInfos:
                if info.DeviceID == scanner_id:
                    device = info.Connect()
                    break
            
            if not device:
                return {"success": False, "error": "Selected scanner not found or could not be connected."}

            # Find and configure the document feeder property
            adf_item = None
            for item in device.Items:
                try:
                    # Check if the feeder is supported
                    if item.Properties.Item(WIA_PROPERTY_DOCUMENT_HANDLING_SELECT).Value & WIA_DOCUMENT_HANDLING_SELECT_FEEDER:
                        item.Properties.Item(WIA_PROPERTY_DOCUMENT_HANDLING_SELECT).Value = WIA_DOCUMENT_HANDLING_SELECT_FEEDER
                        adf_item = item
                        break
                except comtypes.COMError:
                    continue # Property might not exist on all items

            if not adf_item:
                return {"success": False, "error": "ADF (Automatic Document Feeder) is not available or supported on this device."}
            
            scanned_files = []
            page_count = 1
            while True:
                try:
                    # Transfer the image from the feeder
                    image = adf_item.Transfer()
                    if not image:
                        break

                    # Generate a unique filename for each page
                    file_prefix = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
                    filename = f"{file_prefix}_page_{page_count}.{output_format.lower()}"
                    output_path = os.path.join(output_folder, filename)
                    
                    image.SaveFile(output_path)
                    scanned_files.append({"filename": filename, "filepath": output_path})
                    page_count += 1
                
                except comtypes.COMError as e:
                    # Check if the error is "Paper Empty"
                    if e.hresult == WIA_ERROR_PAPER_EMPTY:
                        break  # Stop scanning, as the feeder is empty
                    else:
                        raise  # Re-raise other COM errors

            if not scanned_files:
                return {"success": False, "error": "No pages were scanned. Please ensure documents are in the feeder."}
                
            return {"success": True, "files": scanned_files}

    except comtypes.COMError as e:
        # Handle COM-specific errors, like user cancellation in the dialog
        if "cancelled" in str(e).lower() or e.hresult == -2145320959: # 0x80210001 (WIA_S_CANCEL)
            return {"success": False, "error": "Scan cancelled by user."}
        return {"success": False, "error": f"A scanner communication error occurred: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"An unexpected error occurred during scanning: {str(e)}"}


# Test function to run when the script is executed directly
if __name__ == "__main__":
    print("--- Scanner Module Test ---")
    if platform.system() != 'Windows':
        print("Test skipped: This module is for Windows only.")
    elif not COMTYPES_AVAILABLE:
        print("Test failed: comtypes library is not installed.")
    else:
        print("\n1. Getting available scanners...")
        scanners_result = get_scanners()
        if scanners_result["success"]:
            print(f"   Success! Found {len(scanners_result['scanners'])} scanner(s).")
            for s in scanners_result['scanners']:
                print(f"    - {s['name']} (ID: ...{s['id'][-10:]})")
        else:
            print(f"   Failure: {scanners_result['error']}")
    print("\n--- Test Complete ---")
