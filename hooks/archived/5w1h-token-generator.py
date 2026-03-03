#!/usr/bin/env python3
"""
5W1H Token 生成器
生成和管理 5W1H 對話 Token
"""

import os
import re
import secrets
import string
import sys
from datetime import datetime
from pathlib import Path


def get_token_dir() -> Path:
    """取得 Token 目錄路徑"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    token_dir = project_root / '.claude' / 'hook-logs' / '5w1h-tokens'
    token_dir.mkdir(parents=True, exist_ok=True)
    return token_dir


def generate_5w1h_token() -> str:
    """生成新的 5W1H Token"""
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    # 使用安全的隨機字符生成
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(secrets.choice(chars) for _ in range(6))
    return f"5W1H-{timestamp}-{random_part}"


def save_token(token: str) -> Path:
    """儲存 Token 到檔案"""
    token_dir = get_token_dir()
    session_id = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    token_file = token_dir / f"{session_id}.token"

    content = f"""# 5W1H Session Token
SESSION_START={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
TOKEN={token}
STATUS=active

# 此 Token 用於監控 5W1H 決策框架合規性
# 每次對話回答都必須以此 Token 開頭
"""
    token_file.write_text(content, encoding='utf-8')
    return token_file


def validate_token(token: str) -> bool:
    """驗證 Token 格式"""
    pattern = r'^5W1H-\d{8}-\d{6}-[A-Za-z0-9]{6}$'
    return bool(re.match(pattern, token))


def get_current_token() -> str:
    """取得當前活躍的 Token"""
    token_dir = get_token_dir()
    token_files = sorted(token_dir.glob('*.token'), key=lambda p: p.stat().st_mtime, reverse=True)

    if token_files:
        latest_file = token_files[0]
        try:
            content = latest_file.read_text(encoding='utf-8')
            for line in content.splitlines():
                if line.startswith('TOKEN='):
                    return line.split('=', 1)[1].strip()
        except IOError:
            pass

    return ""


def main():
    args = sys.argv[1:] if len(sys.argv) > 1 else ['generate']
    command = args[0] if args else 'generate'

    if command == 'generate':
        token = generate_5w1h_token()
        token_file = save_token(token)
        print(f"生成新的 5W1H Token: {token}")
        print(f"Token 檔案: {token_file}")
        print(token)

    elif command == 'current':
        current_token = get_current_token()
        if current_token:
            print(current_token)
        else:
            print("無活躍的 Token，建議執行 generate")
            sys.exit(1)

    elif command == 'validate':
        if len(args) < 2:
            print("使用方式: 5w1h-token-generator.py validate <token>")
            sys.exit(1)
        token_to_validate = args[1]
        if validate_token(token_to_validate):
            print(f"Token 格式有效: {token_to_validate}")
            sys.exit(0)
        else:
            print(f"Token 格式無效: {token_to_validate}")
            sys.exit(1)

    else:
        print("使用方式: 5w1h-token-generator.py {generate|current|validate <token>}")
        sys.exit(1)


if __name__ == "__main__":
    main()
