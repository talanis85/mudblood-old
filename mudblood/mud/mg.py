# MorgenGrauen MUD definition

import mud_base
from mud_base import *

class Direction(mud_base.Direction):
    directions = mud_base.Direction.directions + [
            (['ob', 'oben'],    'u'),
            (['u', 'unten'],    'ob'),
            (['rein'],          'raus'),
            (['raus'],          'rein')
            ]

host = "mg.mud.de"
port = 4711
strings['command_not_found'] = "Wie bitte?"

