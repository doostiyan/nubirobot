def string_size_in_mb(s: str) -> float:
    # Encode the string to bytes using UTF-8 encoding
    encoded_string = s.encode('utf-8')
    # Get the size in bytes
    size_in_bytes = len(encoded_string)
    # Convert bytes to megabytes
    size_in_mb = size_in_bytes / (1024 * 1024)
    return size_in_mb