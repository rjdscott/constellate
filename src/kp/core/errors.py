class KnowledgePlaneError(Exception):
    """Base for all kp errors."""


class ConfigError(KnowledgePlaneError):
    """Invalid or missing platform configuration."""


class SeedResolutionError(KnowledgePlaneError):
    """Request lacks any usable seed (no user vector, no seed item)."""
