import os
from enum import Enum


class AnalyzerType(str, Enum):
    """Available analyzer implementations."""
    REPLICATE = "replicate"
    LOCAL = "local"


class Config:
    """
    Backend configuration with environment variable support.
    """
    
    # Analyzer Selection
    ANALYZER_TYPE: AnalyzerType = AnalyzerType(
        os.getenv("ANALYZER_TYPE", "replicate")
    )
    
    # Replicate Configuration
    REPLICATE_API_TOKEN: str | None = os.getenv("REPLICATE_API_TOKEN")
    
    # Image Processing
    DEFAULT_BOX_THRESHOLD: float = float(os.getenv("BOX_THRESHOLD", "0.2"))
    DEFAULT_TEXT_THRESHOLD: float = float(os.getenv("TEXT_THRESHOLD", "0.2"))
    
    # Storage
    DATA_DIR: str = os.getenv("DATA_DIR", "data")
    PROCESSED_DATA_DIR: str = os.getenv("PROCESSED_DATA_DIR", "processed_data")
    
    @classmethod
    def validate(cls) -> None:
        """
        Validate configuration and raise errors for missing required settings.
        """
        if cls.ANALYZER_TYPE == AnalyzerType.REPLICATE:
            if not cls.REPLICATE_API_TOKEN:
                raise ValueError(
                    "REPLICATE_API_TOKEN environment variable is required when "
                    "ANALYZER_TYPE is set to 'replicate'"
                )


config = Config() 