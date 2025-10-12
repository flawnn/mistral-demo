from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .analyzer_interface import ImageAnalyzerInterface

from config import config, AnalyzerType


def create_analyzer() -> "ImageAnalyzerInterface":
    """
    Factory function to create the appropriate image analyzer.
    
    Returns:
        ImageAnalyzerInterface: Configured analyzer instance
        
    Raises:
        ValueError: If analyzer type is not recognized
    """
    if config.ANALYZER_TYPE == AnalyzerType.REPLICATE:
        from .replicate_analyzer import ReplicateAnalyzer
        return ReplicateAnalyzer(api_token=config.REPLICATE_API_TOKEN)
    
    elif config.ANALYZER_TYPE == AnalyzerType.LOCAL:
        from .satellite_analyzer import SatelliteAnalyzer
        return SatelliteAnalyzer()
    
    else:
        raise ValueError(
            f"Unknown analyzer type: {config.ANALYZER_TYPE}. "
            f"Valid options: {', '.join([t.value for t in AnalyzerType])}"
        ) 