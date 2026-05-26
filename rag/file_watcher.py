"""
Obsidian Vault 文件监听器
使用 watchdog 监听 vault 目录变化，自动触发向量库重建。
"""
import threading
import time
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = object


# ── 全局状态 ────────────────────────────────────────────────────────────────
_observer: "Observer | None" = None
_observer_lock = threading.Lock()


def _do_reload() -> None:
    """
    执行向量库重建。
    在独立线程中调用，thread-safe。
    """
    try:
        from rag.rag_engine import build_vector_store
        from rag.obsidian_loader import load_vault_documents

        vault_docs = load_vault_documents()
        # 清空旧数据后重建（强制重建，不复用）
        # 不传 docs，由 build_vector_store 内部统一加载 vault + 内置知识
        build_vector_store(force_rebuild=True)

        from utils.logger_handler import logger
        logger.info(
            f"[Vault-Watcher] 向量库重建完成，"
            f"已同步 {len(vault_docs)} 个 Obsidian 文档。"
        )
    except Exception as e:
        from utils.logger_handler import logger
        logger.error(f"[Vault-Watcher] 重建失败: {e}")


class _VaultReloadHandler(FileSystemEventHandler if WATCHDOG_AVAILABLE else object):
    """监听 vault 目录下 .md 文件的增删改事件，触发向量库重建。"""

    def __init__(self) -> None:
        super().__init__()
        self._debounce_timer: "threading.Timer | None" = None

    def _schedule_reload(self) -> None:
        """防抖：取消pending的重载，等待500ms后再执行。"""
        if self._debounce_timer is not None:
            self._debounce_timer.cancel()
        self._debounce_timer = threading.Timer(0.5, _do_reload)
        self._debounce_timer.start()

    def on_created(self, event) -> None:
        if not event.is_directory and _is_md(event.src_path):
            self._schedule_reload()

    def on_modified(self, event) -> None:
        if not event.is_directory and _is_md(event.src_path):
            self._schedule_reload()

    def on_deleted(self, event) -> None:
        if not event.is_directory and _is_md(event.src_path):
            self._schedule_reload()

    def on_moved(self, event) -> None:
        # 移动/重命名可能是新建+删除
        if not event.is_directory:
            if _is_md(event.src_path) or _is_md(event.dest_path):
                self._schedule_reload()


def _is_md(path: str) -> bool:
    return Path(path).suffix.lower() == ".md"


def start_vault_watcher() -> bool:
    """
    启动 vault 目录监听。
    幂等调用（多次调用只启动一次）。
    返回是否成功启动。
    """
    global _observer

    if not WATCHDOG_AVAILABLE:
        from utils.logger_handler import logger
        logger.warning(
            "[Vault-Watcher] watchdog 未安装，"
            "自动监听功能不可用。请运行: pip install watchdog"
        )
        return False

    with _observer_lock:
        if _observer is not None:
            return True  # 已在运行

        from rag.obsidian_loader import get_vault_dir
        from utils.logger_handler import logger

        vault_dir = get_vault_dir()
        if not vault_dir.exists():
            vault_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[Vault-Watcher] 已创建 vault 目录: {vault_dir}")

        handler = _VaultReloadHandler()
        _observer = Observer()
        _observer.schedule(handler, str(vault_dir), recursive=True)
        _observer.start()

        logger.info(f"[Vault-Watcher] 已启动，监听目录: {vault_dir}")
        return True


def stop_vault_watcher() -> None:
    """停止 vault 监听。"""
    global _observer
    with _observer_lock:
        if _observer is not None:
            _observer.stop()
            _observer.join(timeout=3)
            _observer = None
