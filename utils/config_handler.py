"""
yaml
k:v
"""
import yaml
import os
from utils.path_tool import get_abs_path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def load_rag_config(config_path: str=get_abs_path("config/rag.yml"),encoding: str="utf-8"):
    try:
        with open(config_path,"r",encoding=encoding) as f:
            return yaml.load(f,Loader=yaml.FullLoader)
    except FileNotFoundError:
        return {}


def load_chroma_config(config_path: str=get_abs_path("config/chroma.yml"),encoding: str="utf-8"):
    try:
        with open(config_path,"r",encoding=encoding) as f:
            return yaml.load(f,Loader=yaml.FullLoader)
    except FileNotFoundError:
        return {}


def load_prompts_config(config_path: str=get_abs_path("config/prompts.yml"),encoding: str="utf-8"):
    try:
        with open(config_path,"r",encoding=encoding) as f:
            return yaml.load(f,Loader=yaml.FullLoader) or {}
    except FileNotFoundError:
        return {}


def load_agent_config(config_path: str=get_abs_path("config/agent.yml"),encoding: str="utf-8"):
    try:
        with open(config_path,"r",encoding=encoding) as f:
            return yaml.load(f,Loader=yaml.FullLoader) or {}
    except FileNotFoundError:
        return {}


def load_database_config(config_path: str=get_abs_path("config/database.yml"),encoding: str="utf-8"):
    """
    加载数据库配置（SportsLax 暂不使用，保留接口兼容性）
    """
    try:
        with open(config_path,"r",encoding=encoding) as f:
            config = yaml.load(f,Loader=yaml.FullLoader)
        return config or {}
    except FileNotFoundError:
        return {}


def get_security_config():
    """
    获取安全配置
    """
    return {
        "api_key": os.getenv("API_KEY", ""),
        "cors_origins": os.getenv("CORS_ORIGINS", "").split(","),
        "rate_limit_per_minute": int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    }


rag_conf = load_rag_config()
chroma_conf = load_chroma_config()
prompts_conf = load_prompts_config()
agent_conf = load_agent_config()
db_conf = load_database_config()
security_conf = get_security_config()

if __name__ == '__main__':
    print(rag_conf["chat_model_name"])
