"""Service layer for business logic."""
# Lazy imports to avoid circular dependencies
__all__ = ["ReviewService", "ChatService"]

def __getattr__(name):
    if name == "ReviewService":
        from .review import ReviewService
        return ReviewService
    if name == "ChatService":
        from .chat import ChatService
        return ChatService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

