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

import sys
import os
import re
import getopt

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
    """
    Returns the XML data for a module in a list, one line per list item.
    """

    # Gather information.
    module_dir = os.path.dirname(file_name)
    module_name = os.path.basename(file_name)
    module_te = f"{module_dir}/{module_name}.te"
    module_if = f"{module_dir}/{module_name}.if"

    # Try to open the file, if it cant, just ignore it.
    try:
        module_file = open(module_if)
        module_code = module_file.readlines()
        module_file.close()
    except:
        warning(f"cannot open file {file_name} for read, skipping")
        return []

    module_buf = []

    # Infer the module name, which is the base of the file name.
    module_buf.append(
        f'<module name="{os.path.splitext(os.path.split(file_name)[-1])[0]}" filename="{module_if}">\n'
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
    line_num = 0
    for line in module_code:
        line_num += 1
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
            elif temp_buf:
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
            module_buf.append(f'<{groups[0]} name="{groups[1]}" lineno="{line_num}">\n')

            # Add all the comments attributed to this interface to
            #  the module buffer.
            if temp_buf:
                module_buf += temp_buf
                temp_buf = []

            # Add default summaries and parameters so that the
            #  DTD is happy.
            else:
                warning(
                    f"{file_name}:{line_num}: unable to find XML for {groups[0]} {groups[1]}()"
                )
                module_buf.append("<summary>\n")
                module_buf.append("Summary is missing!\n")
                module_buf.append("</summary>\n")
                module_buf.append('<param name="?">\n')
                module_buf.append("<summary>\n")
                module_buf.append("Parameter descriptions are missing!\n")
                module_buf.append("</summary>\n")
                module_buf.append("</param>\n")

            # Close the interface/template tag.
            module_buf.append(f"</{interface.group(1)}>\n")

            interface = None
            continue

    # If the file just had a header, add the comments to the module buffer.
    if finding_header:
        module_buf += temp_buf
    # Otherwise there are some lingering XML comments at the bottom, warn
    #  the user.
    elif temp_buf:
        warning(f"orphan XML comments at bottom of file {file_name}\n{temp_buf}")

    # Process the TE file if it exists.
    module_buf = module_buf + getTunableXML(module_te, "both")

    module_buf.append("</module>\n")

    return module_buf


def getTunableXML(file_name, kind):
    """
    Return all the XML for the tunables/bools in the file specified.
    """

    # Try to open the file, if it cant, just ignore it.
    try:
        tunable_file = open(file_name)
        tunable_code = tunable_file.readlines()
        tunable_file.close()
    except:
        warning(f"cannot open file {file_name} for read, skipping")
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
                    error(f"{boolean.group(1)} in a {kind} file.")

            tunable_buf.append('<%s name="%s" dftval="%s">\n' % boolean.groups())
            tunable_buf += temp_buf
            temp_buf = []
            tunable_buf.append(f"</{boolean.group(1)}>\n")

    # If there are XML comments at the end of the file, they arn't
    # attributed to anything. These are ignored.
    if temp_buf:
        warning(f"orphan XML comments at bottom of file {file_name}\n{temp_buf}")

    return tunable_buf


def usage():
    """
    Displays a message describing the proper usage of this script.
    """

    print(
        f"usage: {sys.argv[0]} [-w] [-mtb] <file>",
        "",
        "-w --warn\t\t\tshow warnings",
        "-m --module <file>\t\tname of module to process",
        "-t --tunable <file>\t\tname of global tunable file to process",
        "-b --boolean <file>\t\tname of global boolean file to process",
        "",
        "examples:",
        f"> {sys.argv[0]} -w -m policy/modules/apache",
        f"> {sys.argv[0]} -t policy/global_tunables",
    )


def warning(description):
    """
    Warns the user of a non-critical error.
    """

    if warn:
        print(f"{sys.argv[0]}: warning: {description}", file=sys.stderr)


def error(description):
    """
    Describes an error and exists the program.
    """

    print(f"{sys.argv[0]}: error: {description}", file=sys.stderr, flush=True)
    sys.exit(1)


# MAIN PROGRAM

# Defaults
warn = False
module = False
tunable = False
boolean = False

# Check that there are command line arguments.
if len(sys.argv) <= 1:
    usage()
    sys.exit(1)

# Parse command line args
try:
    opts, args = getopt.getopt(
        sys.argv[1:], "whm:t:b:", ["warn", "help", "module=", "tunable=", "boolean="]
    )
except getopt.GetoptError:
    usage()
    sys.exit(2)
for o, a in opts:
    if o in ("-w", "--warn"):
        warn = True
    elif o in ("-h", "--help"):
        usage()
        sys.exit(0)
    elif o in ("-m", "--module"):
        module = a
        break
    elif o in ("-t", "--tunable"):
        tunable = a
        break
    elif o in ("-b", "--boolean"):
        boolean = a
        break
    else:
        usage()
        sys.exit(2)

if module:
    sys.stdout.writelines(getModuleXML(module))
elif tunable:
    sys.stdout.writelines(getTunableXML(tunable, "tunable"))
elif boolean:
    sys.stdout.writelines(getTunableXML(boolean, "bool"))
else:
    usage()
    sys.exit(2)
