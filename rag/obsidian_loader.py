"""
Obsidian Vault 加载器
解析 knowledge/vault/ 目录下的 .md 文件，提取 frontmatter 元数据 + 正文内容
支持 Obsidian 标准格式：YAML frontmatter + Markdown 正文
"""
import re
from pathlib import Path
from typing import Optional
from langchain_core.documents import Document


# ── Vault 目录配置 ──────────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).parent.parent / "knowledge" / "vault"


def load_vault_documents() -> list[Document]:
    """
    扫描 vault 目录下所有 .md 文件，解析并返回 Document 列表。
    递归搜索所有子目录。忽略 .gitkeep 和 .templates 目录。
    """
    docs: list[Document] = []
    if not VAULT_DIR.exists():
        return docs

    for md_file in sorted(VAULT_DIR.rglob("*.md")):
        # 跳过隐藏文件、.templates 目录下的文件
        if any(p.startswith(".") for p in md_file.parts):
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        # 用相对于 vault 的路径作为 filename
        rel_path = md_file.relative_to(VAULT_DIR)
        doc = parse_obsidian_file(str(rel_path), content)
        if doc:
            docs.append(doc)

    return docs


def parse_obsidian_file(filename: str, content: str) -> Optional[Document]:
    """
    解析单个 Obsidian .md 文件。

    支持格式：
        ---
        title: 文档标题
        category: 分类
        tags: [tag1, tag2]
        ---

        # 正文标题

        正文内容...
    """
    # 提取 frontmatter
    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", content, re.DOTALL)

    metadata: dict = {}
    body: str

    if match:
        frontmatter_raw = match.group(1)
        body = match.group(2)

        # 简单 YAML 解析（支持 key: value 和 key: [items]）
        for line in frontmatter_raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip()
                # 去掉列表格式的 [] 和引号
                val = re.sub(r"^\[|\]$", "", val).strip()
                val = re.sub(r"^[\"']|[\"']$", "", val)
                if key and val:
                    metadata[key] = val
    else:
        body = content

    body = body.strip()
    if not body:
        return None

    # 提取标题（从正文第一行 # 标题 或文件名）
    title_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    # 文件名不含路径，只取文件名部分去掉 .md 后缀
    plain_name = Path(filename).stem
    title = (title_match.group(1).strip() if title_match
             else metadata.get("title", plain_name))

    # 构建元数据
    metadata["source"] = f"vault:{title}"
    metadata["filename"] = filename
    if "title" not in metadata:
        metadata["title"] = title

    return Document(page_content=body, metadata=metadata)


def get_vault_dir() -> Path:
    """返回 vault 目录路径。"""
    return VAULT_DIR
