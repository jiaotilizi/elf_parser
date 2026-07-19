class ELFParserError(Exception):
    pass


class ProfileError(ELFParserError):
    pass


class PluginError(ELFParserError):
    pass


class DWARFError(ELFParserError):
    pass


class MemoryReadError(ELFParserError):
    pass


class ResourceNotFoundError(ELFParserError):
    pass
