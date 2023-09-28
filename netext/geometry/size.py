from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Size:
    width: int
    height: int

    def as_tuple(self) -> tuple[int, int]:
        return self.width, self.height
