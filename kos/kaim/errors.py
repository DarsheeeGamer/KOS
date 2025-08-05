"""
KAIM Error definitions
"""


class KAIMError(Exception):
    """Base KAIM error"""
    pass


class KAIMPermissionError(KAIMError):
    """Permission denied error"""
    pass


class KAIMAuthError(KAIMError):
    """Authentication error"""
    pass


class KAIMSessionError(KAIMError):
    """Session-related error"""
    pass


class KAIMDeviceError(KAIMError):
    """Device operation error"""
    pass


class KAIMConnectionError(KAIMError):
    """Connection error"""
    pass