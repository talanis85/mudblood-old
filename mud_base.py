class Direction:
    class NoDirectionError(Exception):
        pass

    NONE = ""
    NORTH = "n"
    NORTHWEST = "nw"
    WEST = "w"
    SOUTHWEST = "sw"
    SOUTH = "s"
    SOUTHEAST = "so"
    EAST = "o"
    NORTHEAST = "no"

    directions = [
            (['n', 'norden'],       's'),
            (['nw', 'nordwesten'],  'so'),
            (['w', 'westen'],       'o'),
            (['sw', 'suedwesten'],  'no'),
            (['s', 'sueden'],       'n'),
            (['so', 'suedosten'],   'nw'),
            (['o', 'osten'],        'w'),
            (['no', 'nordosten'],   'sw'),
        ]

    @classmethod
    def canonical(cls, d):
        for ds in cls.directions:
            if d in ds[0]:
                return ds[0][0]
        return None

    @classmethod
    def calc(cls, d, x, y):
        funcs = {
                cls.NORTH:        lambda x,y: (x, y-1),
                cls.NORTHWEST:    lambda x,y: (x-1, y-1),
                cls.WEST:         lambda x,y: (x-1, y),
                cls.SOUTHWEST:    lambda x,y: (x-1, y+1),
                cls.SOUTH:        lambda x,y: (x, y+1),
                cls.SOUTHEAST:    lambda x,y: (x+1, y+1),
                cls.EAST:         lambda x,y: (x+1, y),
                cls.NORTHEAST:    lambda x,y: (x+1, y-1),
                }

        try:
            return funcs[d](x, y)
        except KeyError:
            raise cls.NoDirectionError()

    @classmethod
    def opposite(cls, d):
        for ds in cls.directions:
            if d in ds[0]:
                return ds[1]
        raise cls.NoDirectionError()

host = "localhost"
port = 9999

strings = {
    'prompt': "> ",
    'command_not_found': "Hae?",
    }
