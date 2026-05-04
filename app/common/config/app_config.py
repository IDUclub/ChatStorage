"""
Module aimed to store app configurations.
"""

from app.common.utils.path_utils import find_project_root


class AppConfig:
    """
    Class for storing app configuration.
    Attributes:
        MONGO_URL (str): Mongo url to access db.
        MONGO_USER (str): Mongo username to access db.
        MONGO_PASSWORD (str): Mongo user password to access db.
        MONGO_DB (str): Mongo db name to access data.
        PROJECT_ROOT (Path): Path to project root content folder.
    """

    def __init__(
        self, mongo_url: str, mongo_user: str, mongo_password: str, mongo_db: str
    ):
        """
        Initialization function for AppConfig class.
        Args:
            mongo_url (str): Mongo url to access db.
            mongo_user (str): Mongo username to access db.
            mongo_password (str): Mongo user password to access db.
            mongo_db (str) :Mongo db name to access data.
        """

        self.MONGO_URL = self.validate_init_parameter(mongo_url, "MONGO_URL")
        self.MONGO_USER = self.validate_init_parameter(mongo_user, "MONGO_USER")
        self.MONGO_PASSWORD = self.validate_init_parameter(
            mongo_password, "MONGO_PASSWORD"
        )
        self.MONGO_DB = self.validate_init_parameter(mongo_db, "MONGO_DB")
        self.PROJECT_ROOT = find_project_root()

    @staticmethod
    def validate_init_parameter(parameter: str, name: str) -> str:
        """
        Function validates weather passed parameter is empty or not.
        Args:
            parameter (str): Parameter to validate in str format.
            name (str): Passed parameter name.
        Returns:
            str: Validated parameter.
        Raises:
            ValueError: Value Error if empty string is passed as parameter.
        """

        if parameter:
            return parameter
        raise ValueError("Passed parameter {} has empty value".format(name, parameter))

    def get_configuration_values(self) -> dict[str, str]:
        """
        Function return dict representation of AppConfiguration.
        Returns:
            dict[str, str]: Dict with key as configuration name and value as configuration value.
        """

        return {
            "MONGO_URL": self.MONGO_URL,
            "MONGO_USER": self.MONGO_USER,
            "MONGO_PASSWORD": self.MONGO_PASSWORD,
            "MONGO_DB": self.MONGO_DB,
            "PROJECT_ROOT": str(self.PROJECT_ROOT),
        }
