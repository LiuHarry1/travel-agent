"""Application constants."""

# File size limits
MAX_FILE_CONTENT_SIZE = 50000  # Maximum content size per file (characters)
MAX_TOTAL_FILE_SIZE = 100000  # Maximum total size for all files (characters)
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB in bytes

# Conversation limits
MAX_CONVERSATION_TURNS = 30  # Maximum number of message turns to keep in history

# Supported file extensions
TEXT_EXTENSIONS = (".txt", ".md", ".json", ".text")
BINARY_EXTENSIONS = (".pdf", ".doc", ".docx")
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS + BINARY_EXTENSIONS

# Binary file markers
BINARY_FILE_PREFIX = "[BINARY_FILE:"
BINARY_FILE_SUFFIX = "]"

