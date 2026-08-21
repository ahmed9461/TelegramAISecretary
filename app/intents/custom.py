from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CustomIntentDefinition:
    id: str
    name: str
    description: str
    examples: tuple[str, ...]
    threshold: float = 0.8
    action_type: str = "NONE"
    action_config: dict | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.threshold <= 1:
            raise ValueError("threshold must be between 0 and 1")
