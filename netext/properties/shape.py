from dataclasses import dataclass
from rich.box import Box as RichBox, ROUNDED


# TODO I am not happy with the API here, to be improved
# Call these classes shapes directly and remove the internal shape classes
# As they are not needed only a shape buffer
@dataclass
class ShapeProperties:
    pass


@dataclass
class JustContentProperties(ShapeProperties):
    pass


@dataclass
class BoxProperties(ShapeProperties):
    box_type: RichBox = ROUNDED
