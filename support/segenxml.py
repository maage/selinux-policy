#!/usr/bin/python

#  Author(s): Donald Miner <dminer@tresys.com>
#      Dave Sugar <dsugar@tresys.com>
#      Brian Williams <bwilliams@tresys.com>
#      Caleb Case <ccase@tresys.com>
#
# Copyright (C) 2005 - 2006 Tresys Technology, LLC
#      This program is free software; you can redistribute it and/or modify
#      it under the terms of the GNU General Public License as published by
#      the Free Software Foundation, version 2.

"""
    This script generates XML documentation information for layers specified
    by the user.
"""

import argparse
import os
import re
import sys
import textwrap

# GLOBALS

# Default values of command line arguments:
warn = False

# Pre compiled regular expressions:

# Matches either an interface or a template declaration. Will give the tuple:
#     ("interface" or "template", name)
# Some examples:
#     "interface(`kernel_read_system_state',`"
#      -> ("interface", "kernel_read_system_state")
#     "template(`base_user_template',`"
#      -> ("template", "base_user_template")
INTERFACE = re.compile(r"^\s*(interface|template)\(`(\w*)'")

# Matches either a gen_bool or a gen_tunable statement. Will give the tuple:
#     ("tunable" or "bool", name, "true" or "false")
# Some examples:
#     "gen_bool(secure_mode, false)"
#      -> ("bool", "secure_mode", "false")
#     "gen_tunable(allow_kerberos, false)"
#      -> ("tunable", "allow_kerberos", "false")
BOOLEAN = re.compile(r"^\s*gen_(tunable|bool)\(\s*(\w*)\s*,\s*(true|false)\s*\)")

# Matches a XML comment in the policy, which is defined as any line starting
#  with two # and at least one character of white space. Will give the single
#  valued tuple:
#     ("comment")
# Some Examples:
#     "## <summary>"
#      -> ("<summary>")
#     "##        The domain allowed access."
#      -> ("The domain allowed access.")
XML_COMMENT = re.compile(r"^##\s+(.*?)\s*$")


# FUNCTIONS
def getModuleXML(file_name):
    '''
    Returns the XML data for a module in a list, one line per list item.
    '''

    # Gather information.
    module_dir = os.path.dirname(file_name)
    module_name = os.path.basename(file_name)
    module_te = "%s/%s.te" % (module_dir, module_name)
    module_if = "%s/%s.if" % (module_dir, module_name)

    # Try to open the file, if it cant, just ignore it.
    try:
        with open(module_if, "r") as module_file:
            module_code = module_file.readlines()
    except IOError:
        warning("cannot open file %s for read, skipping" % file_name)
        return []

    module_buf = []

    # Infer the module name, which is the base of the file name.
    module_buf.append(
        "<module name=\"%s\" filename=\"%s\">\n"
        % (os.path.splitext(os.path.split(file_name)[-1])[0], module_if)
    )

    temp_buf = []
    interface = None

    # finding_header is a flag to denote whether we are still looking
    #  for the XML documentation at the head of the file.
    finding_header = True

    # Get rid of whitespace at top of file
    while module_code and module_code[0].isspace():
        module_code = module_code[1:]

    # Go line by line and figure out what to do with it.
    for line_num, line in enumerate(module_code, start=1):
        if finding_header:
            # If there is a XML comment, add it to the temp buffer.
            comment = XML_COMMENT.match(line)
            if comment:
                temp_buf.append(comment.group(1) + "\n")
                continue

            # Once a line that is not an XML comment is reached,
            #  either put the XML out to module buffer as the
            #  module's documentation, or attribute it to an
            #  interface/template.
            if temp_buf:
                finding_header = False
                interface = INTERFACE.match(line)
                if not interface:
                    module_buf += temp_buf
                    temp_buf = []
                    continue

        # Skip over empty lines
        if line.isspace():
            continue

        # Grab a comment and add it to the temprorary buffer, if it
        #  is there.
        comment = XML_COMMENT.match(line)
        if comment:
            temp_buf.append(comment.group(1) + "\n")
            continue

        # Grab the interface information. This is only not true when
        #  the interface is at the top of the file and there is no
        #  documentation for the module.
        if not interface:
            interface = INTERFACE.match(line)
        if interface:
            # Add the opening tag for the interface/template
            groups = interface.groups()
            module_buf.append(
                "<%s name=\"%s\" lineno=\"%s\">\n" % (groups[0], groups[1], line_num)
            )

            # Add all the comments attributed to this interface to
            #  the module buffer.
            if temp_buf:
                module_buf += temp_buf
                temp_buf = []

            # Add default summaries and parameters so that the
            #  DTD is happy.
            else:
                warning(
                    "%s:%s: unable to find XML for %s %s()"
                    % (file_name, line_num, groups[0], groups[1])
                )
                module_buf.append("<summary>\n")
                module_buf.append("Summary is missing!\n")
                module_buf.append("</summary>\n")
                module_buf.append("<param name=\"?\">\n")
                module_buf.append("<summary>\n")
                module_buf.append("Parameter descriptions are missing!\n")
                module_buf.append("</summary>\n")
                module_buf.append("</param>\n")

            # Close the interface/template tag.
            module_buf.append("</%s>\n" % interface.group(1))

            interface = None
            continue

    # If the file just had a header, add the comments to the module buffer.
    if finding_header:
        module_buf += temp_buf
    # Otherwise there are some lingering XML comments at the bottom, warn
    #  the user.
    elif temp_buf:
        warning("orphan XML comments at bottom of file %s\n%s" % (file_name, temp_buf))

    # Process the TE file if it exists.
    module_buf = module_buf + getTunableXML(module_te, "both")

    module_buf.append("</module>\n")

    return module_buf


def getTunableXML(file_name, kind):
    '''
    Return all the XML for the tunables/bools in the file specified.
    '''

    # Try to open the file, if it cant, just ignore it.
    try:
        with open(file_name, "r") as tunable_file:
            tunable_code = tunable_file.readlines()
    except IOError:
        warning("cannot open file %s for read, skipping" % file_name)
        return []

    tunable_buf = []
    temp_buf = []

    # Find tunables and booleans line by line and use the comments above
    # them.
    for line in tunable_code:
        # If it is an XML comment, add it to the buffer and go on.
        comment = XML_COMMENT.match(line)
        if comment:
            temp_buf.append(comment.group(1) + "\n")
            continue

        # Get the boolean/tunable data.
        boolean = BOOLEAN.match(line)

        # If we reach a boolean/tunable declaration, attribute all XML
        #  in the temp buffer to it and add XML to the tunable buffer.
        if boolean:
            # If there is a gen_bool in a tunable file or a
            # gen_tunable in a boolean file, error and exit.
            # Skip if both kinds are valid.
            if kind != "both":
                if boolean.group(1) != kind:
                    error("%s in a %s file." % (boolean.group(1), kind))

            tunable_buf.append("<%s name=\"%s\" dftval=\"%s\">\n" % boolean.groups())
            tunable_buf += temp_buf
            temp_buf = []
            tunable_buf.append("</%s>\n" % boolean.group(1))

    # If there are XML comments at the end of the file, they arn't
    # attributed to anything. These are ignored.
    if temp_buf:
        warning("orphan XML comments at bottom of file %s\n%s" % (file_name, temp_buf))

    return tunable_buf


def warning(description):
    '''
    Warns the user of a non-critical error.
    '''

    global warn
    if warn:
        sys.stderr.write("%s: " % sys.argv[0])
        sys.stderr.write("warning: " + description + "\n")


def error(description):
    '''
    Describes an error and exists the program.
    '''

    sys.stderr.write("%s: " % sys.argv[0])
    sys.stderr.write("error: " + description + "\n")
    sys.stderr.flush()
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Generate SELinux XML documentation.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            '''\
            examples:
            > %(prog)s -w -m policy/modules/apache
            > %(prog)s -t policy/global_tunables
            '''
        ),
    )
    parser.add_argument(
        '-w', '--warn', dest='warn', action='store_true', help='show warnings'
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '-m',
        '--module',
        dest='module',
        metavar='<module-base-name>',
        help='basename of module to process (without suffix .te)',
    )
    group.add_argument(
        '-t',
        '--tunable',
        dest='tunable',
        metavar='<file>',
        help='name of global tunable file to process',
    )
    group.add_argument(
        '-b',
        '--boolean',
        dest='boolean',
        metavar='<file>',
        help='name of global boolean file to process',
    )
    args = parser.parse_args()

    global warn
    warn = args.warn

    if args.module:
        sys.stdout.writelines(getModuleXML(args.module))
    elif args.tunable:
        sys.stdout.writelines(getTunableXML(args.tunable, "tunable"))
    elif args.boolean:
        sys.stdout.writelines(getTunableXML(args.boolean, "bool"))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
