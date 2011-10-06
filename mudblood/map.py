# $Id$

import time
import pickle
from operator import attrgetter

def instantiate(cls, mud, *args):
    """
        Map, Room and Edge must be intantiated using this method,

        @param cls      The class to intantiate
        @param mud      The mud definition object
        @param *args    Arguments to __init__
        @return         The new object
    """
    return type(cls)(cls.__name__, (cls,), {'mud': mud})(*args)

# ---

class Edge:
    """
        An edge of a graph
    """
    def __init__(self, to, name=""):
        self.to = to
        self.name = name
        self.split = False

class Room:
    """
        A node in the graph
    """
    def __init__(self, text="", tag=""):
        self.text = text
        self.tag = tag

        # TODO: This should really be a set
        self.exits = []
        self.x, self.y = 0, 0
        self.mark = 0
        self.comp = 0
        self.distance = 0

    def __repr__(self):
        return self.tag

    def add_exit(self, room, name):
        """
            Connect two rooms in both directions, thus keeping the graph undirected.

            @param room     The room to connect self to
            @param name     The (canonical) name of the direction
        """
        if room.has_exit(self.mud.Direction.opposite(name)):
            exits = ",".join(map(lambda e: e.name, room.exits))
            raise Map.MapInconsistencyError("Duplicate exit %s in %s. The other room has exits: %s" % (self.mud.Direction.opposite(name), room, exits))
        if self.has_exit(name):
            exits = ",".join(map(lambda e: e.name, self.exits))
            raise Map.MapInconsistencyError("Duplicate exit %s in %s. This room has exits: %s" % (name, room, exits))

        self.exits.append(instantiate(Edge, self.mud, room, name))
        room.exits.append(instantiate(Edge, self.mud, self, self.mud.Direction.opposite(name)))

    def remove_exit(self, name):
        """
            Remove an exit. Again, the opposite direction is also removed.
            
            @param name     The direction to remove
        """
        e = self.get_exit(name)
        if e:
            self.exits.remove(e)
            oe = e.to.get_exit(self.mud.Direction.opposite(name))
            e.to.exits.remove(oe)

    def has_exit(self, name):
        for e in self.exits:
            if e.name == name:
                return True

        return False

    def get_exit(self, name):
        for e in self.exits:
            if e.name == name:
                return e
        return None

    def _update_coords(self, x, y, mark, comp):
        """
            Set the coordinates for this room and recurse to all
            adjacent rooms.

            @param x    The x coordinate
            @param y    The y coordinate
            @param mark A unique value to mark already visited rooms
            @param comp An integer defining the connected component
        """
        self.x = x
        self.y = y
        self.mark = mark
        self.comp = comp

        sx, sy = self.x, self.y

        for e in self.exits:
            if e.to.mark == mark or e.split:
                continue
            try:
                (nx, ny) = self.mud.Direction.calc(e.name, self.x, self.y)
                e.to._update_coords(nx, ny, mark, comp)
            except self.mud.Direction.NoDirectionError:
                pass

# ---

class MapNotification:
    NEW_CYCLE = 1

class Mapper:
    """
        Provides automapping functionality. Client modules should interface with the mapper
        using Mapper.go_to().
    """

    def __init__(self, mud):
        self.mud = mud

        self.map = instantiate(Map, self.mud)
        self.mode = "fixed"
        self.move_stack = []
        self.last_cycle = None

    def go_to(self, direction, text=""):
        """
            Do what is needed to go in a certain direction. When in auto-mode, creates rooms
            as needed. When in fixed-mode, only updates current_room.

            @param direction    The direction to move
            @param text         Text to associate with the room (unused)
            @return             None or a MapNotification to indicate a special condition.
                                (such as a new cycle)
        """
        self.last_cycle = None

        if self.mode == "off":
            return

        if self.map.current_room:
            if self.map.current_room.has_exit(direction):
                self.map.current_room = self.map.current_room.get_exit(direction).to
                self.move_stack.append((self.map.current_room, direction, 0))
            else:
                if self.mode != "auto":
                    return

                self.map.update_coords()
                new_room = instantiate(Room, self.mud, text)

                try:
                    (x, y) = self.mud.Direction.calc(direction, self.map.current_room.x, self.map.current_room.y)

                    for r in self.map.rooms:
                        if (r.x, r.y, r.comp) == (x, y, self.map.current_room.comp):
                            self.last_cycle = (self.map.current_room, new_room, direction)
                            try:
                                self.map.current_room.add_exit(r, direction)
                            except Map.MapInconsistencyError:
                                self.last_cycle = None
                                self.map.add(new_room)
                                self.map.current_room.add_exit(new_room, direction)
                                self.map.current_room = new_room
                                self.move_stack.append((self.map.current_room, direction, 2))
                                return

                            self.map.current_room = r
                            self.move_stack.append((self.map.current_room, direction, 1))
                            return MapNotification.NEW_CYCLE
                except self.mud.Direction.NoDirectionError:
                    pass

                self.map.add(new_room)
                self.map.current_room.add_exit(new_room, direction)
                self.map.current_room = new_room
                self.move_stack.append((self.map.current_room, direction, 2))
        else:
            if self.mode != "auto":
                return
            self.map.current_room = self.map.add(instantiate(Room, self.mud, text))
            self.move_stack.append((self.map.current_room, direction, 2))

    def find_shortest_path(self, target_tag):
        from heapq import heappush,heappop

        target = None
        for r in self.map.rooms:
            if r.tag == target_tag:
                target = r
        if not target:
            return None

        self.map.current_room.shortest_path = []
        pq = [(0, self.map.current_room)]
        mark = time.time()

        while len(pq) > 0:
            curdist, curroom = heappop(pq)
            curroom.mark = mark
            curroom.distance = curdist
            for e in curroom.exits:
                if e.to.mark != mark or e.to.distance > curdist + 1:
                    e.to.mark = mark
                    e.to.shortest_path = curroom.shortest_path + [e.name]
                    heappush(pq, (curdist + 1, e.to))

        if target.mark == mark:
            return target.shortest_path
        else:
            return None

    def undo(self):
        """
            Undo the last action.
        """
        r, d, t = self.move_stack.pop()

        self.map.current_room = self.move_stack[-1][0]

        if t >= 1:
            self.map.current_room.remove_exit(d)
        if t == 2:
            self.map.rooms.remove(r)

        return (r, d, t)

    # COMMANDS

    def command(self, cmd, args):
        if cmd == "":
            return False

        if hasattr(self, "cmd_" + cmd):
            return getattr(self, "cmd_" + cmd)(args)
        else:
            return False

    def cmd_undo(self, args):
        self.undo()

    def cmd_clear(self, args):
        self.map.rooms = []
        return "Map cleared."

    def cmd_nocycle(self, args):
        # TODO: use self.undo()
        if self.last_cycle == None:
            return "There was no cycle"

        last_room, new_room, d = self.last_cycle
        last_room.remove_exit(d)
        last_room.add_exit(self.map.add(new_room), d)
        self.map.current_room = new_room
        self.last_cycle = None

        return "Ok."

    def cmd_opposite(self, args):
        r, d, t = self.move_stack[-1]
        r.remove_exit(self.mud.self.mud.Direction.opposite(d))
        r.add_exit(self.move_stack[-2][0], args[0])

        return "Changed way back to: " + args[0]

    def cmd_mode(self, args):
        if args == []:
            return "Mapper mode: " + self.mode

        if args[0] in ['fixed', 'auto', 'off']:
            self.mode = args[0]
            return "Mapper mode: " + self.mode
        else:
            return "Valid modes are: fixed, auto, off"

    def cmd_move(self, args):
        if args == []:
            return "Move where?"

        e = self.map.current_room.get_exit(args[0])
        if e:
            self.map.current_room = e.to
            return True
        else:
            return "There is no way to go " + args[0]

    def cmd_tag(self, args):
        if args == []:
            if self.map.current_room.tag == "":
                return "This room has no tag."
            else:
                return "This room is tagged: %s" % self.map.current_room.tag
        else:
            self.map.current_room.tag = args[0]
            return "Tagged this room as: %s" % args[0]

    def cmd_goto(self, args):
        if args == []:
            return "Go to which tag?"
        else:
            for r in self.map.rooms:
                if r.tag == args[0]:
                    self.map.current_room = r
                    return "Ok."
            return "Tag %s not found." % args[0]

    def cmd_save(self, args):
        if len(args) > 0:
            self.map.name = args[0]
        if self.map.name == "":
            return "Please give a map name."

        with open("maps/%s" % self.map.name, "w") as f:
            pickle.dump(self.map, f)
        return "Ok."

    def cmd_load(self, args):
        if args == []:
            return "Load which map?"
        with open("maps/%s" % args[0], "r") as f:
            self.map = pickle.load(f)

        self.map.mud = self.mud
        for r in self.map.rooms:
            r.mud = self.mud

        return "Map %s loaded." % args[0]

    def cmd_new(self, args):
        self.__init__(self.mud)
        if len(args) > 0:
            self.map.name = args[0]
        return "New map."

    def cmd_cycle(self, args):
        if args == []:
            return "Build a cycle where?"

        for r in self.map.rooms:
            if r.tag == args[0]:
                d = self.move_stack[-1][1]
                self.undo()
                self.map.current_room.add_exit(r, d)
                self.map.current_room = r
                return "Ok. Built cycle to %s." % r.tag
        return "Tag not found."

    def cmd_split(self, args):
        r1,r2,d = self.move_stack[-2][0], self.move_stack[-1][0], self.move_stack[-1][1]
        r1.get_exit(d).split = True
        r2.get_exit(self.mud.Direction.opposite(d)).split = True
        return "Ok."
    
class Map:
    """
        The Map
    """
    class MapInconsistencyError(Exception):
        pass

    def __init__(self):
        self.name = ""
        self.rooms = []
        self.current_room = None

    def __repr__(self):
        r = ""
        for c in self.render():
            if not r == "":
                r += "\n"
            r += c + "\n"
        return r

    def add(self, room):
        """
            Add a room to the map.

            @param room     The room to add.
            @return         Just that room.
        """
        self.rooms.append(room);
        return room

    def update_coords(self):
        if self.rooms == []:
            return 0

        mark = time.time()
        comp = 0

        # To render the graph, we have to assign each room a coordinate value that should
        # reflect the topology of the game reasonably good. For this, we do a DFS on every
        # Room we haven't visited so far (Room._update_coords()). Each DFS gives us coordinates
        # for a single connected component of the graph.
        for r in self.rooms:
            if r.mark != mark:
                r._update_coords(0, 0, mark, comp)
                comp += 1

        return comp


    def render(self):
        """
            Render the map to ASCII.

            @return     A list of strings, each forming a single line.
        """

        comp = self.update_coords()

        allret = []
        bridges = []

        # Now that we have all coordinates, we can draw the map
        for c in range(comp):
            comprooms = filter(lambda r: r.comp == c, self.rooms)

            minx = min([r.x for r in comprooms])
            miny = min([r.y for r in comprooms])
            maxx = max([r.x for r in comprooms])
            maxy = max([r.y for r in comprooms])

            w = maxx - minx
            h = maxy - miny

            for r in comprooms:
                r.x -= minx
                r.y -= miny

            ret = []
            for i in range((h+1) * 3):
                ret.append(bytearray("   " * (w+1), "ascii"))

            for r in comprooms:
                char = ' '
                bridge = 0

                for e in r.exits:
                    try:
                        self.mud.Direction.calc(e.name, 0, 0)
                    except self.mud.Direction.NoDirectionError:
                        for i in range(len(bridges)):
                            if e.to in bridges[i]:
                                bridges[i].add(r)
                                bridge = i+1
                        if bridge == 0:
                            bridges.append(set([r]))
                            bridge = len(bridges)


                if self.current_room == r:
                    char = "X"
                elif bridge:
                    char = chr(ord("A")+bridge-1)
                else:
                    char = "#"
                ret[r.y * 3 + 1][r.x * 3 + 1] = char


            def vert(orig):
                m = { ' ': '|',
                      '|': '|',
                      '-': '+',
                      '_': '+',
                      '\\': '|',
                      '/': '|' }
                if orig in m:
                    return m[orig]
                else:
                    return orig
            
            def horiz(orig):
                m = { ' ': '-',
                      '|': '+',
                      '-': '-',
                      '_': '-',
                      '\\': '-',
                      '/': '-' }
                if orig in m:
                    return m[orig]
                else:
                    return orig
            
            def diag1(orig):
                m = { ' ': '\\',
                      '|': '|',
                      '-': '-',
                      '_': '_',
                      '\\': '\\',
                      '/': 'X' }
                if orig in m:
                    return m[orig]
                else:
                    return orig

            def diag2(orig):
                m = { ' ': '/',
                      '|': '|',
                      '-': '-',
                      '_': '_',
                      '\\': 'X',
                      '/': '/' }
                if orig in m:
                    return m[orig]
                else:
                    return orig


            for r in comprooms:
                e = r.get_exit(self.mud.Direction.SOUTH)
                if e and e.to.comp == c:
                    cy = r.y * 3 + 1 + 1
                    cx = r.x * 3 + 1
                    if e.to.x == r.x:
                        while cy < h * 3 + 1 and chr(ret[cy][cx]) not in ['#', 'X']:
                            ret[cy][cx] = vert(chr(ret[cy][cx]))
                            cy += 1
                    elif e.to.x > r.x:
                        ret[cy][cx] = "|"
                        cx += 1
                        while cx < e.to.x * 3 + 1:
                            ret[cy][cx] = "_"
                            cx += 1
                        cy += 1
                        ret[cy][cx] = "|"
                    elif e.to.x < r.x:
                        ret[cy][cx] = "|"
                        cx -= 1
                        while cx < e.to.x * 3 + 1:
                            ret[cy][cx] = "_"
                            cx -= 1
                        cy += 1
                        ret[cy][cx] = "|"

                e = r.get_exit(self.mud.Direction.EAST)
                if e and e.to.y == r.y and e.to.comp == c:
                    cy = r.y * 3 + 1
                    cx = r.x * 3 + 1 + 1
                    while cx < w * 3 + 1 and chr(ret[cy][cx]) not in ['#', 'X']:
                        ret[cy][cx] = horiz(chr(ret[cy][cx]))
                        cx += 1

                e = r.get_exit(self.mud.Direction.SOUTHEAST)
                if e and e.to.comp == c:
                    cy = r.y * 3 + 1 + 1
                    cx = r.x * 3 + 1 + 1
                    if e.to.y-e.to.x == r.y-r.x:
                        while cx < w * 3 + 1 and cy < h * 3 + 1 and chr(ret[cy][cx]) not in ['#', 'X']:
                            ret[cy][cx] = diag1(chr(ret[cy][cx]))
                            cx += 1
                            cy += 1
                    else:
                        ret[cy][cx] = "\\"
                        cx += 1
                        while cx < e.to.x * 3 + 1:
                            ret[cy][cx] = "_"
                            cx += 1
                        while cy < e.to.y * 3 - 1:
                            ret[cy][cx] = "|"
                            cy += 1
                        cy += 1
                        ret[cy][cx] = "\\"

                e = r.get_exit(self.mud.Direction.SOUTHWEST)
                if e and e.to.comp == c:
                    cy = r.y * 3 + 1 + 1
                    cx = r.x * 3 + 1 - 1
                    if e.to.y+e.to.x == (r.y+r.x):
                        while cx >= 0 and cy < h * 3 + 1 and chr(ret[cy][cx]) not in ['#', 'X']:
                            ret[cy][cx] = diag2(chr(ret[cy][cx]))
                            cx -= 1
                            cy += 1
                    else:
                        ret[cy][cx] = "/"
                        cx -= 1
                        while cx > e.to.x * 3 + 2:
                            ret[cy][cx] = "_"
                            cx -= 1
                        cy += 1
                        while cy < e.to.y * 3:
                            ret[cy][cx] = "|"
                            cy += 1
                        ret[cy][cx] = "/"

            allret.extend([str(l) for l in ret])
            allret.append("")

        return allret
