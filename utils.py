# Utilities

def scan_dict(src: dict, key: str, value: str):
    """
    Scan dictionary for key and get the first occurrence
    of key containing value == value
    """
    if isinstance(src, dict):
        if key in src:
            if src[key] == value or isinstance(src[key], list) and value in src[key]:
                return src
        for key_i in src.keys():
            result = scan_dict(src[key_i], key, value)
            if result:
                return result
    elif isinstance(src, list):
        for item in src:
            result = scan_dict(item, key, value)
            if result:
                return result
    return None

if __name__ == "__main__":
    mydict = {'a': 1, 'b': 2, 'c': [6, 4, 5], 'e': {'c': 3}}
    print(scan_dict(mydict, key='c', value=3))