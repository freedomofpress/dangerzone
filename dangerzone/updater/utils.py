def write(file, content: bytes | str):
    file.write(content)
    file.flush()
