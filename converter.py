import os
import sys
import json


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
    python_script = sys.argv[1]

    try:
        user_file_name = sys.argv[2]
    except (AttributeError, IndexError) as e:
        user_file_name = "micro_python"

    file_name_with_path = "micro_bit/{}.py".format(user_file_name)

    file_path = check_or_create_working_dir(filepath=file_name_with_path)
    if file_path:
        write_python_code_on_file(code=python_script, filepath=file_name_with_path)
