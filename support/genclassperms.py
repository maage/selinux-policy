#!/usr/bin/python

# Author: Donald Miner <dminer@tresys.com>
#
# Copyright (C) 2005 Tresys Technology, LLC
#      This program is free software; you can redistribute it and/or modify
#      it under the terms of the GNU General Public License as published by
#      the Free Software Foundation, version 2.


"""
    This script generates an object class perm definition file.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

USERSPACE_CLASS = "userspace"


@dataclass
class Class:
    """
    This object stores an access vector class.
    """

    name: str
    perms: list[str]
    common: bool


def get_perms(name, av_db, common):
    """
    Returns the list of permissions contained within an access vector
    class that is stored in the access vector database av_db.
    Returns an empty list if the object name is not found.
    Specifiy whether get_perms is to return the class or the
    common set of permissions with the boolean value 'common',
    which is important in the case of having duplicate names (such as
    class file and common file).
    """

    # Traverse through the access vector database and try to find the
    #  object with the name passed.
    for obj in av_db:
        if obj.name == name and obj.common == common:
            return obj.perms

    return []


def get_av_db(file_name):
    """
    Returns an access vector database generated from the file file_name.
    """
    # This function takes a file, reads the data, parses it and returns
    #  a list of access vector classes.
    # Reading into av_data:
    #  The file specified will be read line by line. Each line will have
    #   its comments removed. Once comments are removed, each 'word' (text
    #   seperated by whitespace) and braces will be split up into seperate
    #   strings and appended to the av_data list, in the order they were
    #   read.
    # Parsing av_data:
    #  Parsing is done using a queue implementation of the av_data list.
    #   Each time a word is used, it is dequeued afterwards. Each loop in
    #   the while loop below will read in key words and dequeue expected
    #   words and values. At the end of each loop, a Class containing the
    #   name, permissions and whether it is a common or not will be appended
    #   to the database. Lots of errors are caught here, almost all checking
    #   if a token is expected but EOF is reached.
    # Now the list of Class objects is returned.

    av_data = []
    with open(file_name) as av_file:
        # Read the file and strip out comments on the way.
        # At the end of the loop, av_data will contain a list of individual
        #  words. i.e. ['common', 'file', '{', ...]. All comments and whitespace
        #  will be gone.
        for av_line in av_file:
            # Check if there is a comment, and if there is, remove it.
            av_line, _, _ = av_line.partition("#")

            # Pad the braces with whitespace so that they are split into
            #  their own word. It doesn't matter if there will be extra
            #  white space, it'll get thrown away when the string is split.
            av_line.replace("{", " { ")
            av_line.replace("}", " } ")

            # Split up the words on the line and add it to av_data.
            av_data += av_line.split()

    # Parsing the file:
    # The implementation of this parse is a queue. We use the list of words
    #  from av_data and use the front element, then dequeue it. Each
    #  loop of this while is a common or class declaration. Several
    #  expected tokens are parsed and dequeued out of av_data for each loop.
    # At the end of the loop, database will contain a list of Class objects.
    #  i.e. [Class('name',['perm1','perm2',...],'True'), ...]
    # Dequeue from the beginning of the list until av_data is empty:
    database = []
    while av_data:
        # At the beginning of every loop, the next word should be
        #  "common" or "class", meaning that each loop is a common
        #  or class declaration.
        # av_data = av_data[1:] removes the first element in the
        #  list, this is what is dequeueing data.

        # Figure out whether the next class will be a common or a class.
        # Dequeue the "class" or "common" key word.
        tok = av_data.pop(0)
        if tok not in ("class", "common"):
            error(f"Unexpected token in file {file_name}: {tok}.")

        common = bool(tok == "common")

        if not av_data:
            error(f"Missing token in file {file_name}.")

        # Get and dequeue the name of the class or common.
        name = av_data.pop(0)

        # Retrieve the permissions inherited from a common set:
        perms = []
        # If the object we are working with is a class, since only
        #  classes inherit:
        if not common:
            if not av_data:
                error(f"Missing token in file {file_name}.")

            # If the class inherits from something else:
            if av_data[0] == "inherits":
                # Dequeue the "inherits" key word.
                av_data.pop(0)

                if not av_data:
                    error(f"Missing token in file {file_name} for {name}.")

                # Dequeue the name of the parent.
                tok = av_data.pop(0)

                # tok is the name of the parent.
                # Append the permissions of the parent to
                #  the current class' permissions.
                perms += get_perms(tok, database, True)

        # Retrieve the permissions defined with this set.
        if av_data and av_data[0] == "{":
            # Dequeue the "{"
            tok = av_data.pop(0)

            # Keep appending permissions until a close brace is
            #  found.
            while av_data:
                # Dequeue next token.
                tok = av_data.pop(0)

                if tok == "}":
                    break

                if tok == "{":
                    error(f"Extra '{{' in file {file_name}.")

                # Add the permission name.
                perms.append(tok)

            if tok != "}":
                error(f"Missing token '}}' in file {file_name}.")

        # Add the new access vector class to the database.
        database.append(Class(name, perms, common))

    return database


def get_sc_db(file_name):
    """
    Returns a security class database generated from the file file_name.
    """

    database = []

    # Read the file then close it.
    with open(file_name) as sc_file:
        # For each line in the security classes file, add the name of the class
        #  and whether it is a userspace class or not to the security class
        #  database.
        for line in sc_file:
            line = line.lstrip()

            # If the line is empty or the entire line is a comment, skip.
            if line == "" or line[0] == "#":
                continue

            # Check if the comment to the right of the permission matches
            #  USERSPACE_CLASS.
            line, _, comment = line.partition("#")
            userspace = bool(comment.strip() == USERSPACE_CLASS)

            # All lines should be in the format "class NAME", meaning
            #  it should have two tokens and the first token should be
            #  "class".
            split_line = line.split()
            if len(split_line) < 2 or split_line[0] != "class":
                error(f"Wrong syntax: {line}")

            # Add the class's name (split_line[1]) and whether it is a
            #  userspace class or not to the database.
            # This is appending a tuple of (NAME,USERSPACE), where NAME is
            #  the name of the security class and USERSPACE is True if
            #  if it has "# USERSPACE_CLASS" on the end of the line, False
            #  if not.
            database.append((split_line[1], userspace))

    return database


def gen_class_perms(av_db, sc_db):
    """
    Generates a class permissions document and returns it.
    """

    # Define class template:
    class_perms_line = "define(`all_%s_perms',`{ %s }')"

    # Generate the defines for the individual class permissions.
    class_perms = []
    for obj in av_db:
        # Don't output commons
        if obj.common:
            continue

        # Get the list of permissions from the specified class.
        perms = get_perms(obj.name, av_db, False)

        # Merge all the permissions into one string with one space
        #  padding.
        perm_str = " ".join(perms)

        # Add the line to the class_perms
        class_perms.append(class_perms_line % (obj.name, perm_str))

    # Generate the kernel_class_perms and userspace_class_perms sets.
    class_line = "\tclass %s all_%s_perms;"
    kernel_class_perms = ["define(`all_kernel_class_perms',`"]
    userspace_class_perms = ["define(`all_userspace_class_perms',`"]
    # For each (NAME,USERSPACE) tuple, add the class to the appropriate
    #  class permission set.
    for name, userspace in sc_db:
        if userspace:
            userspace_class_perms.append(class_line % (name, name))
        else:
            kernel_class_perms.append(class_line % (name, name))
    kernel_class_perms.append("')")
    userspace_class_perms.append("')")

    # Throw all the strings together and return the string.
    return "\n".join(
        [*class_perms, "", *kernel_class_perms, "", *userspace_class_perms]
    )


def error(msg):
    """
    Print an error message and exit.
    """

    print(f"{sys.argv[0]} exiting for: {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


def main():
    if len(sys.argv) != 3:
        error(
            f"Incorrect input.\nUsage: {sys.argv[0]} access_vector_file security_class_file"
        )

    access_vector_file, security_class_file = sys.argv[1], sys.argv[2]

    # Output the class permissions document.
    print(
        gen_class_perms(get_av_db(access_vector_file), get_sc_db(security_class_file))
    )


if __name__ == "__main__":
    main()
