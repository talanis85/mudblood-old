#!/usr/bin/env python
# $Id$

# mudblood - A mud client
#
# Copyright (c) 2011 Philip Kranz

from __future__ import absolute_import

import sys, os
import mudblood.interfaces.serial, mudblood.interfaces.urwid

from optparse import OptionParser

VERSION = "0.1"

def main():
    parser = OptionParser(usage="Usage: %prog [options] <host> <port>",
                          version="mudblood " + VERSION)

    parser.add_option("-i", "--interface",
                      action =  "store",
                      dest =    "interface",
                      type =    "choice",
                      choices = ["serial", "curses"],
                      default = "serial",
                      help =    "Choices: serial (default) or curses",)

    parser.add_option("-p", "--prefix",
                      action =  "store",
                      dest =    "prefix",
                      type =    "string",
                      default = ".",
                      help =    "Command Prefix (default: '.')")


    (options, args) = parser.parse_args()

    if len(args) == 1:
        mud = __import__("mudblood.mud_base")
        if os.path.exists(os.path.expanduser("~/.config/mudblood/" + args[0])):
            execfile(os.path.expanduser("~/.config/mudblood/" + args[0]), mud.__dict__)
        else:
            print "MUD definition not found"
            sys.exit(1)
    elif len(args) == 2:
        mud = __import__("mud_base")
        mud.host = args[0]
        mud.port = int(args[1])
    else:
        mud = None

    iface = None

    if options.interface == "serial":
        iface = mudblood.interfaces.serial
    elif options.interface == "curses":
        iface = mudblood.interfaces.urwid
    else:
        print "Interface not known"
        sys.exit(1)

    iface.args = args
    iface.options = options
    r = iface.Interface(mud).run()

    if r == -1:
        parser.print_usage()
        sys.exit(1)

main()