import os

from fastapi import UploadFile
from .BaseController import BaseController
from .ProjectController import ProjectController
from models import ResponseEnums
import re


class DataController(BaseController):
    def __init__(self):
        super().__init__()
        self.size_scale = 1024 * 1024  # 1 MB in bytes

    def validate_file(self, file: UploadFile):

        if file.content_type not in self.settings.ALLOWED_EXTENSIONS:
            return False, ResponseEnums.ERROR.value

        if file.size > self.settings.FILE_MAX_SIZE * self.size_scale:
            return False, ResponseEnums.ERROR.value

        return True, ResponseEnums.SUCCESS.value

    def generate_unique_filepath(self, original_filename: str, project_id: str):
        random_filename = self.generate_random_string()
        project_path = ProjectController().get_project_path(project_id=project_id)

        random_key = self.generate_random_string()
        cleaned_filename = self.clean_filename(original_filename)

        file_path = os.path.join(project_path, f"{random_key}_{cleaned_filename}")

        while os.path.exists(file_path):
            random_key = self.generate_random_string()
            file_path = os.path.join(project_path, f"{random_key}_{cleaned_filename}")

        return file_path, f"{random_key}_{cleaned_filename}"

    def clean_filename(self, original_filename: str):
        cleaned_filename = re.sub(r"[^\w.]", "", original_filename.strip())
        cleaned_filename = cleaned_filename.replace(" ", "_")
        return cleaned_filename
