# -*- coding: utf-8 -*-
"""富宝账号凭据的本地加密存储（Windows DPAPI）。

与根目录 run_f139.ps1 / code/sync_f139.ps1 使用同一份 cred.dat：
- 文件内容是 DPAPI 加密后的十六进制字符串；
- 明文格式为 UTF-16LE 的「用户名\\n密码」；
- 只有当前 Windows 用户能解密，不写入数据库、不记录日志。
"""
import binascii
import datetime as dt
import os
from typing import Optional, Tuple

try:
    import win32crypt
except ImportError:  # pragma: no cover - 仅在缺少 pywin32 时触发
    win32crypt = None

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(SERVER_DIR)
CODE_DIR = os.path.dirname(APP_DIR)
PROJECT_ROOT = os.path.dirname(CODE_DIR)
CRED_FILE = os.path.join(PROJECT_ROOT, 'cred.dat')
DESCRIPTION = 'f139 credentials'


def _require_dpapi() -> None:
    if win32crypt is None:
        raise RuntimeError('缺少 pywin32，无法使用 Windows DPAPI 加密保存凭据')


def read_credentials() -> Optional[Tuple[str, str]]:
    """读取 cred.dat，返回 (用户名, 密码)；文件不存在或无法解密时返回 None。"""
    if not os.path.exists(CRED_FILE) or win32crypt is None:
        return None
    try:
        raw = open(CRED_FILE, 'r', encoding='ascii').read().strip()
        blob = binascii.unhexlify(raw)
        _, data = win32crypt.CryptUnprotectData(blob, None, None, None, 0)
        text = data.decode('utf-16-le')
    except Exception:
        return None
    parts = text.split('\n', 1)
    if len(parts) != 2:
        return None
    username = parts[0].strip()
    password = parts[1]
    if not username or not password:
        return None
    return username, password


def save_credentials(username: str, password: str) -> None:
    """把用户名/密码用 DPAPI 加密写入 cred.dat（格式与 PowerShell 脚本兼容）。"""
    _require_dpapi()
    username = (username or '').strip()
    if not username or not password:
        raise ValueError('用户名或密码为空')
    text = ('%s\n%s' % (username, password)).encode('utf-16-le')
    blob = win32crypt.CryptProtectData(text, DESCRIPTION, None, None, None, 0)
    os.makedirs(os.path.dirname(CRED_FILE), exist_ok=True)
    temp_path = CRED_FILE + '.tmp'
    with open(temp_path, 'w', encoding='ascii', newline='') as fh:
        fh.write(binascii.hexlify(blob).decode('ascii'))
    os.replace(temp_path, CRED_FILE)


def clear_credentials() -> None:
    try:
        if os.path.exists(CRED_FILE):
            os.remove(CRED_FILE)
    except OSError:
        pass
    os.environ.pop('F139_USERNAME', None)
    os.environ.pop('F139_PASSWORD', None)


def mask_username(username: str) -> str:
    text = (username or '').strip()
    if not text:
        return ''
    if len(text) <= 4:
        return text[:1] + '***'
    return text[:3] + '****' + text[-2:]


def status() -> dict:
    """返回可安全展示的凭据状态，不包含密码或完整用户名。"""
    try:
        creds = read_credentials()
    except Exception:
        creds = None
    updated_at = ''
    if os.path.exists(CRED_FILE):
        try:
            updated_at = dt.datetime.fromtimestamp(
                os.path.getmtime(CRED_FILE)).strftime('%Y-%m-%d %H:%M:%S')
        except OSError:
            updated_at = ''
    return {
        'configured': bool(creds),
        'username': mask_username(creds[0]) if creds else '',
        'filePath': os.path.basename(CRED_FILE),
        'updatedAt': updated_at,
    }


def load_into_env() -> bool:
    """把凭据注入当前进程环境变量，供 f139.ensure_token 自动续期使用。"""
    creds = read_credentials()
    if not creds:
        return False
    os.environ['F139_USERNAME'] = creds[0]
    os.environ['F139_PASSWORD'] = creds[1]
    return True


def subprocess_env() -> dict:
    """返回带凭据的子进程环境，避免子进程每次都要重新解密。"""
    env = os.environ.copy()
    creds = read_credentials()
    if creds:
        env['F139_USERNAME'] = creds[0]
        env['F139_PASSWORD'] = creds[1]
    return env
