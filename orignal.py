from __future__ import print_function
import binascii
import ctypes
import os
import struct
import sys
from subprocess import check_output
import time
import json
from runtime import _RUNTIME

can_minify = True

try:
    import nudatus
except ImportError:  # pragma: no cover
    can_minify = False

#: The magic start address in flash memory for a Python script.
_SCRIPT_ADDR = 0x3e000


#: The help text to be shown when requested.
_HELP_TEXT = """
                """


#: MAJOR, MINOR, RELEASE, STATUS [alpha, beta, final], VERSION of uflash
_VERSION = (1, 2, 4, )
_MAX_SIZE = 8188


#: The version number reported by the bundled MicroPython in os.uname().
MICROPYTHON_VERSION = '1.0.1'


def strfunc(raw):
    return str(raw) if sys.version_info[0] == 2 else str(raw, 'utf-8')


def hexlify(script, minify=False):
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

    # Convert to .hex format.
    output = [':020000040003F7']  # extended linear address, 0x0003.
    addr = _SCRIPT_ADDR
    for i in range(0, len(data), 16):
        chunk = data[i:min(i + 16, len(data))]
        chunk = struct.pack('>BHB', len(chunk), addr & 0xffff, 0) + chunk
        checksum = (-(sum(bytearray(chunk)))) & 0xff
        hexline = ':%s%02X' % (strfunc(binascii.hexlify(chunk)).upper(),
                               checksum)
        output.append(hexline)
        addr += 16
    return '\n'.join(output)


def embed_hex(runtime_hex, python_hex=None):
    if not runtime_hex:
        print(json.dumps({"message": 'MicroPython runtime hex required.'}))
        raise ValueError('MicroPython runtime hex required.')
    if not python_hex:
        return runtime_hex
    py_list = python_hex.split()
    runtime_list = runtime_hex.split()
    embedded_list = []
    # The embedded list should be the original runtime with the Python based
    # hex embedded two lines from the end.
    embedded_list.extend(runtime_list[:-5])
    embedded_list.extend(py_list)
    embedded_list.extend(runtime_list[-5:])
    return '\n'.join(embedded_list) + '\n'


def find_microbit():
    # Check what sort of operating system we're on.
    if os.name == 'posix':
        # 'posix' means we're on Linux or OSX (Mac).
        # Call the unix "mount" command to list the mounted volumes.
        mount_output = check_output('mount').splitlines()
        mounted_volumes = [x.split()[2] for x in mount_output]
        for volume in mounted_volumes:
            if volume.endswith(b'MICROBIT'):
                return volume.decode('utf-8')  # Return a string not bytes.
    elif os.name == 'nt':
        # 'nt' means we're on Windows.

        def get_volume_name(disk_name):
            vol_name_buf = ctypes.create_unicode_buffer(1024)
            ctypes.windll.kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p(disk_name), vol_name_buf,
                ctypes.sizeof(vol_name_buf), None, None, None, None, 0)
            return vol_name_buf.value
        old_mode = ctypes.windll.kernel32.SetErrorMode(1)
        try:
            for disk in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                path = '{}:\\'.format(disk)
                #
                # Don't bother looking if the drive isn't removable
                #
                # if ctypes.windll.kernel32.GetDriveTypeW(path) != 2:
                #     continue
                if os.path.exists(path) and \
                        get_volume_name(path) == 'MICROBIT':
                    return path
        finally:
            ctypes.windll.kernel32.SetErrorMode(old_mode)
    else:
        # No support for unknown operating systems.
        print(json.dumps({"message": 'OS "{}" not supported.'.format(os.name)}))
        raise NotImplementedError('OS "{}" not supported.'.format(os.name))


def save_hex(hex_file, path):
    if not hex_file:
        print(json.dumps({"message": 'Cannot flash an empty .hex file.'}))
        raise ValueError('Cannot flash an empty .hex file.')
    if not path.endswith('.hex'):
        print(json.dumps({"message": 'The path to flash must be for a .hex file.'}))
        raise ValueError('The path to flash must be for a .hex file.')
    with open(path, 'wb') as output:
        output.write(hex_file.encode('ascii'))


def converter(path_to_python=None, paths_to_microbits=None,
          path_to_runtime=None, python_script=None, minify=False):
    # Check for the correct version of Python.
    if not ((sys.version_info[0] == 3 and sys.version_info[1] >= 3) or
            (sys.version_info[0] == 2 and sys.version_info[1] >= 7)):
        print(json.dumps({"message": 'Will only run on Python 2.7, or 3.3 and later.'}))
        raise RuntimeError('Will only run on Python 2.7, or 3.3 and later.')
    # Grab the Python script (if needed).
    python_hex = ''
    python_file_name = ""
    if path_to_python:
        if not path_to_python.endswith('.py'):
            print(json.dumps({"message": 'Python files must end in ".py".'}))
            raise ValueError('Python files must end in ".py".')
        with open(path_to_python, 'rb') as python_script:
            python_file_name = os.path.splitext(path_to_python)[0]
            python_hex = hexlify(python_script.read(), minify)
    elif python_script:
        python_file_name = "my_hex"
        python_hex = hexlify(python_script, minify)

    runtime = _RUNTIME
    # Load the hex for the runtime.
    if path_to_runtime:
        with open(path_to_runtime) as runtime_file:
            runtime = runtime_file.read()
    # Generate the resulting hex file.
    micropython_hex = embed_hex(runtime, python_hex)

    # Save File in our current/customized location with python file name

    file_name = "microbit/{0}.hex".format(python_file_name)
    if not os.path.exists(os.path.dirname(file_name)):
        try:
            os.makedirs(os.path.dirname(file_name))
        except OSError as exc:  # Guard against race condition
            print(exc)

    with open(file_name, "w") as f:
        f.write(micropython_hex)

    # Find the micro:bit.
    if not paths_to_microbits:
        found_microbit = find_microbit()
        if found_microbit:
            paths_to_microbits = [found_microbit]
    # Attempt to write the hex file to the micro:bit.
    if paths_to_microbits:
        for path in paths_to_microbits:
            hex_path = os.path.join(path, 'micropython.hex')
            save_hex(micropython_hex, hex_path)
        # time.sleep(10)
        print(json.dumps({"message": 'Yayy.. You did it !!!'}))
    else:
        print(json.dumps({"message": 'Micro:bit not found !'}))


if __name__ == '__main__':
    python_script = sys.argv[1]
    try:
        user_file_name = sys.argv[2]
    except:
        user_file_name = "micropython"
    file_name = "microbit_exa/{}.py".format(user_file_name)
    # print(json.dumps({user_file_name})
    if not os.path.exists(os.path.dirname(file_name)):
        try:
            os.makedirs(os.path.dirname(file_name))
        except OSError as exc:  # Guard against race condition
            print(exc)
    with open(file_name, "w") as f:
        f.write(sys.argv[1])
    # flash(python_script=python_script)
    converter('microbit_exa/{}.py'.format(user_file_name))