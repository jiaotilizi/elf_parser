from typing import Dict, Any


class DisplayFactory:
    @staticmethod
    def create(scheme: str, profile: Dict[str, Any], data_adapter=None):
        if scheme == 'cli_basic':
            from .cli_basic import CliBasicDisplay
            return CliBasicDisplay(profile, data_adapter)
        elif scheme == 'cli_interactive':
            from .cli_interactive import CliInteractiveDisplay
            return CliInteractiveDisplay(profile, data_adapter)
        elif scheme == 'web_gui':
            from .web_gui import WebGuiDisplay
            return WebGuiDisplay(profile, data_adapter)
        else:
            from .cli_basic import CliBasicDisplay
            return CliBasicDisplay(profile, data_adapter)
    
    @staticmethod
    def get_supported_schemes():
        return ['cli_basic', 'cli_interactive', 'web_gui']