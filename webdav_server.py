#!/usr/bin/env python3
"""
WebDAV 服务 — 将 knowledge/vault/ 目录暴露为远程挂载点
客户通过 Obsidian Remote Save 插件远程管理知识库
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# vault 绝对路径
VAULT_DIR = Path(__file__).parent / "knowledge" / "vault"
VAULT_DIR.mkdir(parents=True, exist_ok=True)

# WebDAV 配置
config = {
    "host": "0.0.0.0",
    "port": 8081,
    "provider_mapping": {
        "/": {
            "root": str(VAULT_DIR),
            "readonly": False,
            "auth": {
                "accept_basic": True,
                "accept_digest": False,
            },
        },
    },
    "simple_dc": {
        "user_mapping": {
            "*": {
                os.getenv("WEBDAV_USER", "sportslaw_user"): {
                    "password": os.getenv("WEBDAV_PASSWORD", "change_me_please"),
                    "description": "Vault 知识库用户",
                    "roles": ["editor"],
                }
            }
        }
    },
    "verbose": 1 if os.getenv("WEBDAV_VERBOSE") else 0,
    "dir_browser": {
        "enable": False,
    },
}

if __name__ == "__main__":
    from wsgidav.wsgidav_app import WsgiDAVApp
    from cheroot.wsgi import Server as CherootServer

    app = WsgiDAVApp(config)
    server = CherootServer((config["host"], config["port"]), app)

    print(f"[WebDAV] 服务启动: http://{config['host']}:{config['port']}/")
    print(f"[WebDAV] 挂载目录: {VAULT_DIR}")
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
