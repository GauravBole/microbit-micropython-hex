import os
import sys
import json
import struct
import binascii

from runtime import _RUNTIME

can_minify = True

#: The magic start address in flash memory for a Python script.
_SCRIPT_ADDR = 0x3e000

_MAX_SIZE = 8188


try:
    import nudatus
except ImportError:
    can_minify = False


def strfunc(raw_string):
    # convert utf-8
    return str(raw_string) if sys.version_info[0] == 2 else str(raw_string, 'utf-8')


def check_python_version():

    if not ((sys.version_info[0] == 3 and sys.version_info[1] >= 3) or
            (sys.version_info[0] == 2 and sys.version_info[1] >= 7)):
        print(json.dumps({"message": 'Will only run on Python 2.7, or 3.3 and later.'}))
        raise RuntimeError('Will only run on Python 2.7, or 3.3 and later.')


def hex_convert(data: bytes) -> []:
    # Convert to .hex format.

    output = [':020000040003F7']  # extended linear address, 0x0003.
    addr = _SCRIPT_ADDR
    for i in range(0, len(data), 16):
        chunk = data[i:min(i + 16, len(data))]
        chunk = struct.pack('>BHB', len(chunk), addr & 0xffff, 0) + chunk
        checksum = (-(sum(bytearray(chunk)))) & 0xff
        hex_line = ':%s%02X' % (strfunc(binascii.hexlify(chunk)).upper(), checksum)
        output.append(hex_line)
        addr += 16
    return output


def hexlify(script: bytes, minify: bool = False):
    if not script:
        return ''

    # Convert line endings in case the file was created on Windows.
    script = script.replace(b'\r\n', b'\n')
    script = script.replace(b'\r', b'\n')

    # Remove comments and extra code with nudatus if minify specifed

    if minify:
        if not can_minify:
            raise ValueError("No minifier is available")
        script = nudatus.mangle(script.decode('utf-8')).encode('utf-8')

    # Add header, pad to multiple of 16 bytes.
    data = b'MP' + struct.pack('<H', len(script)) + script

    # Padding with null bytes in a 2/3 compatible way
    data = data + (b'\x00' * (16 - len(data) % 16))
    if len(data) > _MAX_SIZE:
        # 'MP' = 2 bytes, script length is another 2 bytes.
        print(json.dumps({"message": 'Python script must be less than 8188 bytes.'}))
        raise ValueError("Python script must be less than 8188 bytes.")

    output = hex_convert(data=data)
    return '\n'.join(output)


def python_code_to_hex(python_terminal_code: bytes = None, minify=False):

    if python_terminal_code:
        python_file_name = "my_hex"
        python_hex = hexlify(python_terminal_code, minify)
        return python_hex


def converter(python_terminal_code: str = None):
    check_python_version()
    python_hex = python_code_to_hex(python_terminal_code=python_terminal_code)


def check_or_create_working_dir(filepath: str) -> bool:
    if not os.path.exists(os.path.dirname(filepath)):
        try:
            os.makedirs(os.path.dirname(filepath))
        except OSError as exc:
            print(exc)
            return False
        return True


def write_python_code_on_file(code: str, filepath: str) -> bool:
    try:
        with open(filepath, "w") as f:
            f.write(code)
        return True
    except (FileExistsError, FileNotFoundError):
        return False


if __name__ == '__main__':
    """
     Required 2 parameter First is string of micro-python code and second file-name
    """

    python_script = sys.argv[1]

    try:
        user_file_name = sys.argv[2]
    except (AttributeError, IndexError) as e:
        user_file_name = "micro_python"

    file_name_with_path = "micro_bit/{}.py".format(user_file_name)

    file_path = check_or_create_working_dir(filepath=file_name_with_path)
    if file_path:
        write_python_code_on_file(code=python_script, filepath=file_name_with_path)

    converter(file_name_with_path)
