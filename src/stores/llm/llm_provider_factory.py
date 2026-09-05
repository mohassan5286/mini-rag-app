from .llm_enum import LLMEnum
from .providers import CoHereProvider, OpenAIProvider


class LLMProviderFactory:
    def __init__(self, configs):
        self.configs = configs

    def create_provider(self, provider: str):
        if provider == LLMEnum.OPENAI.value:
            return OpenAIProvider(
                api_key=self.configs.OPENAI_API_KEY, 
                api_url=self.configs.OPENAI_API_URL, 
                default_input_max_characters=self.configs.DEFAULT_INPUT_MAX_CHARACTERS, 
                default_output_max_tokens=self.configs.DEFAULT_OUTPUT_MAX_TOKENS,    
                default_generation_temperature=self.configs.GENERATION_DAFAULT_TEMPERATURE
            )
        elif provider == LLMEnum.COHERE.value:
            return CoHereProvider(
                api_key=self.configs.COHERE_API_KEY, 
                default_input_max_characters=self.configs.DEFAULT_INPUT_MAX_CHARACTERS, 
                default_output_max_tokens=self.configs.DEFAULT_OUTPUT_MAX_TOKENS,
                default_generation_temperature=self.configs.GENERATION_DAFAULT_TEMPERATURE
            )

        return None
    