import mud_base
from mud_base import *

class Direction(mud_base.Direction):
    directions = mud_base.Direction.directions + [
            (['oben'],          'unten'),
            (['unten'],         'oben'),
            (['rein'],          'raus'),
            (['raus'],          'rein')
            ]

host = "localhost"
port = 9999
strings["command_not_found"] = "Hae?"

