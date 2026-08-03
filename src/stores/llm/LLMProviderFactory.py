from .LLMEnums import LLMEnums
from stores.llm.providers.OpenAIProvider import OpenAIProvider
from stores.llm.providers.CoHereProvider import CoHereProvider

class LLMProviderFactory():
    def __init__(self, configs):
        self.configs = configs

    def create_provider(self, provider: str):
        if provider == LLMEnums.OPENAI.value:
            return OpenAIProvider(
                api_key=self.configs.OPENAI_API_KEY, 
                api_url=self.configs.OPENAI_API_URL, 
                default_input_max_characters=self.configs.DEFAULT_INPUT_MAX_CHARACTERS, 
                default_output_max_characters=self.configs.DEFAULT_OUTPUT_MAX_CHARACTERS,    
                default_generation_temperature=self.configs.GENERATION_DAFAULT_TEMPERATURE
            )
        elif provider == LLMEnums.COHERE.value:
            return CoHereProvider(
                api_key=self.configs.COHERE_API_KEY, 
                default_input_max_characters=self.configs.DEFAULT_INPUT_MAX_CHARACTERS, 
                default_output_max_characters=self.configs.DEFAULT_OUTPUT_MAX_CHARACTERS,    
                default_generation_temperature=self.configs.GENERATION_DAFAULT_TEMPERATURE
            )

        return None