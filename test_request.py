import urllib.request

url = "http://127.0.0.1:5000/view/Shubham/9f0e4d35-2ac1-4a85-a233-de260400980f_WhatsApp_Image_2023-08-14_at_18.25.25.jpg"
print('Requesting:', url)
try:
    resp = urllib.request.urlopen(url)
    print('STATUS:', resp.status)
    print('HEADERS:')
    for k, v in resp.getheaders():
        print(f"{k}: {v}")
    data = resp.read(100)
    print('READ_BYTES:', len(data))
except Exception as e:
    print('ERROR:', repr(e))
