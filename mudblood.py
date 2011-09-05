#!/usr/bin/env python
# $Id$

# mudblood - A mud client
#
# Copyright (c) 2011 Philip Kranz

from __future__ import absolute_import

import sys
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

    if options.interface == "serial":
        mudblood.interfaces.serial.options = options
        s = mudblood.interfaces.serial.Serial()
        r = s.run()

    elif options.interface == "curses":
        mudblood.interfaces.urwid.options = options
        mudblood.interfaces.urwid.args = args
        s = mudblood.interfaces.urwid.Urwid()
        r = s.run()

    else:
        print "Interface not known"
        sys.exit(1)

    if r == -1:
        parser.print_usage()
        sys.exit(1)

main()
