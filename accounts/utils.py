from urllib.parse import unquote

def decode_filename(file_url):
    return unquote(file_url)
