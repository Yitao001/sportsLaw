from abc import ABC, abstractmethod
from typing import Optional
import os
from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from utils.logger_handler import logger

load_dotenv()


class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        pass


class ChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[BaseChatModel]:
        """
        根据配置创建对话模型
        支持：tongyi（通义千问）、openai（GPT）、claude（Anthropic）、siliconflow（硅基流动）等
        """
        model_provider = os.getenv("MODEL_PROVIDER", "tongyi")
        model_name = os.getenv("CHAT_MODEL_NAME", "qwen-max")
        
        logger.info(f"[模型工厂] 正在加载对话模型: {model_provider}/{model_name}")
        
        if model_provider == "tongyi":
            from langchain_community.chat_models.tongyi import ChatTongyi
            return ChatTongyi(model=model_name)
        
        elif model_provider == "openai":
            from langchain_openai import ChatOpenAI
            api_key = os.getenv("OPENAI_API_KEY", "")
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            return ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=base_url
            )
        
        elif model_provider == "siliconflow":
            from langchain_openai import ChatOpenAI
            api_key = os.getenv("SILICONFLOW_API_KEY", "")
            base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
            return ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=base_url
            )
        
        elif model_provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            api_key = os.getenv("ANTHROPIC_API_KEY", "")
            return ChatAnthropic(
                model=model_name,
                api_key=api_key
            )
        
        else:
            raise ValueError(f"不支持的模型提供商: {model_provider}")


class EmbeddingsFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings]:
        """
        根据配置创建向量嵌入模型
        """
        model_provider = os.getenv("MODEL_PROVIDER", "tongyi")
        model_name = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-v4")
        
        logger.info(f"[模型工厂] 正在加载嵌入模型: {model_provider}/{model_name}")
        
        if model_provider == "tongyi":
            from langchain_community.embeddings import DashScopeEmbeddings
            return DashScopeEmbeddings(model=model_name)
        
        elif model_provider == "openai":
            from langchain_openai import OpenAIEmbeddings
            api_key = os.getenv("OPENAI_API_KEY", "")
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            return OpenAIEmbeddings(
                model=model_name,
                api_key=api_key,
                base_url=base_url
            )
        
        elif model_provider == "siliconflow":
            from langchain_openai import OpenAIEmbeddings
            api_key = os.getenv("SILICONFLOW_API_KEY", "")
            base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
            return OpenAIEmbeddings(
                model=model_name,
                api_key=api_key,
                base_url=base_url
            )
        
        else:
            raise ValueError(f"不支持的嵌入模型提供商: {model_provider}")


def chat_model():
    """
    创建并返回对话模型实例
    """
    return ChatModelFactory().generator()


def embed_model():
    """
    创建并返回嵌入模型实例
    """
    return EmbeddingsFactory().generator()
