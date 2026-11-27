import winreg


def read_hook(name: str) -> str:
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Proof") as key:
        value, _ = winreg.QueryValueEx(key, name)
    return str(value)
