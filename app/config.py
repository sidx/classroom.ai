import os
import yaml
from typing import Dict, Any
from functools import lru_cache

class Config:
    def __init__(self, config_data: Dict[str, Any]):
        self.data = config_data
        self.openai = OpenAIConfig(config_data)

class OpenAIConfig:
    def __init__(self, config_data: Dict[str, Any]):
        self.api_key = config_data.get('openai_gpt4o_api_key')

@lru_cache()
def get_config() -> Config:
    """Get application configuration, using cache to avoid repeated file reads"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'default.yaml')
    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f)
    return Config(config_data)
