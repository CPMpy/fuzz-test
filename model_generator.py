

import subprocess

if __name__ == '__main__':
    result = None
    try:
        result = subprocess.Popen("python -m pytest cpmpytests", capture_output=True, text=True)
    except KeyboardInterrupt:
        result.kill()
    

