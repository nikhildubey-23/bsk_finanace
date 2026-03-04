from scanner import scan_document

print("Testing Scanner...")
result = scan_document(
    scanner_id='{6BDD1FC6-810F-11D0-BEC7-08002BE2092F}\\0000',
    output_format='jpg',
    output_folder='uploads/temp'
)
print(f"Result: {result}")
