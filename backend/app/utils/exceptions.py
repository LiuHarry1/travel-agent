"""Custom exceptions and error handling utilities."""

from typing import Optional


class MRTReviewError(Exception):
    """Base exception for MRT Review application."""
    pass


class FileProcessingError(MRTReviewError):
    """Exception raised when file processing fails."""
    pass


class ConfigurationError(MRTReviewError):
    """Exception raised when configuration is invalid."""
    pass


def format_error_message(error: Exception, default_message: str = "An error occurred") -> str:
    """
    Format error message for user display.
    
    Args:
        error: The exception that occurred
        default_message: Default message if error message is empty
        
    Returns:
        Formatted error message
    """
    error_str = str(error)
    if not error_str:
        return default_message
    
    # Handle DNS/network resolution errors
    if "nodename nor servname provided" in error_str or "not known" in error_str:
        return (
            "Network connection error: Unable to resolve server address. "
            "This may be due to: 1) Network connectivity issues 2) DNS resolution problems "
            "3) Firewall or proxy blocking the connection. "
            "Please check your network connection and try again."
        )
    elif "Connection reset" in error_str or "Connection reset by peer" in error_str:
        return (
            "Connection was reset. This might be due to large file size or network instability. "
            "Please try: 1) Upload smaller files 2) Check network connection 3) Retry later"
        )
    elif "timeout" in error_str.lower() or "timed out" in error_str.lower():
        return (
            "Request timeout: Processing took too long. "
            "Please try uploading smaller files or upload in batches."
        )
    elif "Connection" in error_str or "connect" in error_str.lower():
        return (
            "Connection error: Unable to connect to AI service. "
            "Please check network connection or retry later."
        )
    elif "Name or service not known" in error_str or "getaddrinfo failed" in error_str:
        return (
            "DNS resolution error: Unable to resolve the server address. "
            "Please check your network connection and DNS settings."
        )
    
    return error_str

