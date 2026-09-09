import os

class TemplateParser:

    def __init__(self, language: str=None, default_language='en'):
        self.current_path = os.path.dirname(os.path.abspath(__file__))
        self.default_language = default_language
        self.language = None
        self.set_language(language if language else self.default_language)
    
    def set_language(self, language: str):
        self.language = language
        language_path = os.path.join(self.current_path, "locales", language)
        if not os.path.exists(language_path):
            self.language = self.default_language
            

    def get(self, group: str, key: str, vars: dict={}):
        if not group or not key:
            return None

        if not os.path.exists(os.path.join(self.current_path, "locales", self.language, f"{group}.py")):
            return None 

        modules = __import__(f"stores.llm.templates.locales.{self.language}.{group}", fromlist=[key])

        if not modules:
            return None

        return getattr(modules, key).substitute(vars)
