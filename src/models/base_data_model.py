from helpers.config import get_settings


class BaseDataModel:

    def __init__(self, db_client: object):
        self.settings = get_settings()
        self.db_client = db_client 
