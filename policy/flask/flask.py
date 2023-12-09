#!/usr/bin/python -E
#
# Author(s): Caleb Case <ccase@tresys.com>
#
# Adapted from the bash/awk scripts mkflask.sh and mkaccess_vector.sh
#

import getopt
import os
import re
import sys


class ParseError(Exception):
    def __init__(self, type, file, line):
        self.type = type
        self.file = file
        self.line = line

    def __str__(self):
        typeS = self.type
        if not isinstance(self.type, str):
            typeS = Flask.CONSTANT_S[self.type]
        return "Parse Error: Unexpected %s on line %d of %s." % (
            typeS,
            self.line,
            self.file,
        )


class DuplicateError(Exception):
    def __init__(self, type, file, line, symbol):
        self.type = type
        self.file = file
        self.line = line
        self.symbol = symbol

    def __str__(self):
        typeS = self.type
        if not isinstance(self.type, str):
            typeS = Flask.CONSTANT_S[self.type]
        return "Duplicate Error: Duplicate %s '%s' on line %d of %s." % (
            typeS,
            self.symbol,
            self.line,
            self.file,
        )


class UndefinedError(Exception):
    def __init__(self, type, file, line, symbol):
        self.type = type
        self.file = file
        self.line = line
        self.symbol = symbol

    def __str__(self):
        typeS = self.type
        if not isinstance(self.type, str):
            typeS = Flask.CONSTANT_S[self.type]
        return "Undefined Error: %s '%s' is not defined but used on line %d of %s." % (
            typeS,
            self.symbol,
            self.line,
            self.file,
        )


class UnusedError(Exception):
    def __init__(self, info):
        self.info = info

    def __str__(self):
        return f"Unused Error: {self.info}"


class Flask:
    """
    FLASK container class with utilities for parsing definition
    files and creating c header files.
    """

    # Constants used in definitions parsing.
    WHITE = re.compile(r"^\s*$")
    COMMENT = re.compile(r"^\s*#")
    USERFLAG = re.compile(r"# userspace")
    CLASS = re.compile(r"^class (?P<name>\w+)")
    COMMON = re.compile(r"^common (?P<name>\w+)")
    INHERITS = re.compile(r"^inherits (?P<name>\w+)")
    OPENB = re.compile(r"^{")
    VECTOR = re.compile(r"^\s*(?P<name>\w+)")
    CLOSEB = re.compile(r"^}")
    SID = re.compile(r"^sid (?P<name>\w+)")
    EOF = "end of file"

    # Constants used in header generation.
    USERSPACE = 0
    KERNEL = 1

    CONSTANT_S = {  # parsing constants
        WHITE: "whitespace",
        COMMENT: "comment",
        USERFLAG: "userspace flag",
        CLASS: "class definition",
        COMMON: "common definition",
        INHERITS: "inherits definition",
        OPENB: "'{'",
        VECTOR: "access vector definition",
        CLOSEB: "'}'",
        SID: "security identifier",
        EOF: "end of file",  # generation constants
        USERSPACE: "userspace mode",
        KERNEL: "kernel mode",
    }

    def __init__(self, warn=True):
        self.WARN = warn
        self.autogen = "/* This file is automatically generated.  Do not edit. */\n"
        self.commons = []
        self.user_commons = []
        self.common = {}
        self.classes = []
        self.vectors = []
        self.vector = {}
        self.userspace = {}
        self.sids = []
        self.inherits = {}

    def warning(self, msg):
        """
        Prints a warning message out to stderr if warnings are enabled.
        """
        if self.WARN:
            print(f"Warning: {msg}", file=sys.stderr)

    def parseClasses(self, path):
        """
        Parses security class definitions from the given path.
        """
        classes = []
        with open(path) as inp:
            number = 0
            for line in inp:
                number += 1
                m = self.COMMENT.search(line)
                if m:
                    continue

                m = self.WHITE.search(line)
                if m:
                    continue

                m = self.CLASS.search(line)
                if m:
                    g = m.groupdict()
                    c = g["name"]
                    if c in classes:
                        raise DuplicateError(self.CLASS, path, number, c)
                    classes.append(c)
                    if self.USERFLAG.search(line):
                        self.userspace[c] = True
                    else:
                        self.userspace[c] = False
                    continue

                msg = "data.  Was expecting either a comment, whitespace, or class definition. "
                raise ParseError(msg, path, number)

        self.classes = classes
        return classes

    def parseSids(self, path):
        """
        Parses initial SID definitions from the given path.
        """

        sids = []
        with open(path) as inp:
            number = 0
            for line in inp:
                number += 1
                m = self.COMMENT.search(line)
                if m:
                    continue

                m = self.WHITE.search(line)
                if m:
                    continue

                m = self.SID.search(line)
                if m:
                    g = m.groupdict()
                    s = g["name"]
                    if s in sids:
                        raise DuplicateError(self.SID, path, number, s)
                    sids.append(s)
                    continue

                msg = "data. Was expecting either a comment, whitespace, or security identifier. "
                raise ParseError(msg, path, number)

            self.sids = sids

        return sids

    def parseVectors(self, path):
        """
        Parses access vector definitions from the given path.
        """
        vectors = []
        vector = {}
        commons = []
        common = {}
        inherits = {}
        user_commons = {}

        # states
        NONE = 0
        COMMON = 1
        CLASS = 2
        INHERIT = 3
        OPEN = 4

        state = NONE
        state2 = NONE
        number = 0
        with open(path) as inp:
            for line in inp:
                number += 1
                m = self.COMMENT.search(line)
                if m:
                    continue

                m = self.WHITE.search(line)
                if m:
                    if state == INHERIT:
                        state = NONE
                    continue

                m = self.COMMON.search(line)
                if m:
                    if state != NONE:
                        raise ParseError(self.COMMON, path, number)
                    g = m.groupdict()
                    c = g["name"]
                    if c in commons:
                        raise DuplicateError(self.COMMON, path, number, c)
                    commons.append(c)
                    common[c] = []
                    user_commons[c] = True
                    state = COMMON
                    continue

                m = self.CLASS.search(line)
                if m:
                    if state != NONE:
                        raise ParseError(self.CLASS, number)
                    g = m.groupdict()
                    c = g["name"]
                    if c in vectors:
                        raise DuplicateError(self.CLASS, path, number, c)
                    if c not in self.classes:
                        raise UndefinedError(self.CLASS, path, number, c)
                    vectors.append(c)
                    vector[c] = []
                    state = CLASS
                    continue

                m = self.INHERITS.search(line)
                if m:
                    if state != CLASS:
                        raise ParseError(self.INHERITS, number)
                    g = m.groupdict()
                    i = g["name"]
                    if c in inherits:
                        raise DuplicateError(self.INHERITS, path, number, c)
                    if i not in common:
                        raise UndefinedError(self.COMMON, path, number, i)
                    inherits[c] = i
                    state = INHERIT
                    if not self.userspace[c]:
                        user_commons[i] = False
                    continue

                m = self.OPENB.search(line)
                if m:
                    if (state not in (CLASS, INHERIT, COMMON)) or state2 != NONE:
                        raise ParseError(self.OPENB, path, number)
                    state2 = OPEN
                    continue

                m = self.VECTOR.search(line)
                if m:
                    if state2 != OPEN:
                        raise ParseError(self.VECTOR, path, number)
                    g = m.groupdict()
                    v = g["name"]
                    if state in (CLASS, INHERIT):
                        if v in vector[c]:
                            raise DuplicateError(self.VECTOR, path, number, v)
                        vector[c].append(v)
                    elif state == COMMON:
                        if v in common[c]:
                            raise DuplicateError(self.VECTOR, path, number, v)
                        common[c].append(v)
                    continue

                m = self.CLOSEB.search(line)
                if m:
                    if state2 != OPEN:
                        raise ParseError(self.CLOSEB, path, number)
                    state = NONE
                    state2 = NONE
                    c = None
                    continue

                msg = "data"
                raise ParseError(msg, path, number)

        if NONE not in (state, state2):
            raise ParseError(self.EOF, path, number)

        cvdiff = set(self.classes) - set(vectors)
        if cvdiff:
            # the inverse of this will be caught as an undefined class error
            msg = f"Not all security classes were used in access vectors: {cvdiff}"
            raise UnusedError(msg)

        self.commons = commons
        self.user_commons = user_commons
        self.common = common
        self.vectors = vectors
        self.vector = vector
        self.inherits = inherits
        return vector

    def createHeaders(self, path, mode=USERSPACE):
        """
        Creates the C header files in the specified MODE and outputs
        them to give PATH.
        """
        headers = {
            "av_inherit.h": self.createAvInheritH(mode),
            "av_perm_to_string.h": self.createAvPermToStringH(mode),
            "av_permissions.h": self.createAvPermissionsH(mode),
            "class_to_string.h": self.createClassToStringH(mode),
            "common_perm_to_string.h": self.createCommonPermToStringH(mode),
            "flask.h": self.createFlaskH(mode),
            "initial_sid_to_string.h": self.createInitialSidToStringH(mode),
        }

        for key, value in headers.items():
            with open(os.path.join(path, key), "w") as of:
                of.writelines(value)

    def createUL(self, count):
        fields = [1, 2, 4, 8]
        return f"0x{fields[count % 4] << 4 * (count / 4):08x}UL"

    def createAvInheritH(self, mode=USERSPACE):
        """ """
        results = []
        results.append(self.autogen)
        for c in self.vectors:
            if c in self.inherits:
                i = self.inherits[c]
                count = len(self.common[i])
                if not (mode == self.KERNEL and self.userspace[c]):
                    results.append(
                        f"   S_(SECCLASS_{c.upper()}, {i}, {self.createUL(count)})\n"
                    )
        return results

    def createAvPermToStringH(self, mode=USERSPACE):
        """ """
        results = []
        results.append(self.autogen)
        for c in self.vectors:
            for p in self.vector[c]:
                if not (mode == self.KERNEL and self.userspace[c]):
                    results.append(
                        f'   S_(SECCLASS_{c.upper()}, {c.upper()}__{p.upper()}, "{p}")\n'
                    )

        return results

    def createAvPermissionsH(self, mode=USERSPACE):
        """ """
        results = []
        results.append(self.autogen)

        width = 57
        count = 0
        for common in self.commons:
            count = 0
            for p in self.common[common]:
                if not (mode == self.KERNEL and self.user_commons[common]):
                    columnA = f"#define COMMON_{common.upper()}__{p.upper()} "
                    columnA += "".join([" " for i in range(width - len(columnA))])
                    results.append(f"{columnA}{self.createUL(count)}\n")
                    count += 1

        width = 50  # broken for old tools whitespace
        for c in self.vectors:
            count = 0

            ps = []
            if c in self.inherits:
                ps += self.common[self.inherits[c]]
            ps += self.vector[c]
            for p in ps:
                columnA = f"#define {c.upper()}__{p.upper()} "
                columnA += "".join([" " for i in range(width - len(columnA))])
                if not (mode == self.KERNEL and self.userspace[c]):
                    results.append(f"{columnA}{self.createUL(count)}\n")
                count += 1

        return results

    def createClassToStringH(self, mode=USERSPACE):
        """ """
        results = []
        results.append(self.autogen)
        results.append("/*\n * Security object class definitions\n */\n")

        if mode == self.KERNEL:
            results.append("    S_(NULL)\n")
        else:
            results.append('    S_("null")\n')

        for c in self.classes:
            if mode == self.KERNEL and self.userspace[c]:
                results.append("    S_(NULL)\n")
            else:
                results.append(f'    S_("{c}")\n')
        return results

    def createCommonPermToStringH(self, mode=USERSPACE):
        """ """
        results = []
        results.append(self.autogen)
        for common in self.commons:
            if not (mode == self.KERNEL and self.user_commons[common]):
                results.append(f"TB_(common_{common}_perm_to_string)\n")
                for p in self.common[common]:
                    results.append(f'    S_("{p}")\n')
                results.append(f"TE_(common_{common}_perm_to_string)\n\n")
        return results

    def createFlaskH(self, mode=USERSPACE):
        """ """
        results = []
        results.append(self.autogen)
        results.append("#ifndef _SELINUX_FLASK_H_\n")
        results.append("#define _SELINUX_FLASK_H_\n")
        results.append("\n")
        results.append("/*\n")
        results.append(" * Security object class definitions\n")
        results.append(" */\n")

        count = 0
        width = 57
        for c in self.classes:
            count += 1
            columnA = f"#define SECCLASS_{c.upper()} "
            columnA += "".join([" " for i in range(width - len(columnA))])
            if not (mode == self.KERNEL and self.userspace[c]):
                results.append("%s%d\n" % (columnA, count))

        results.append("\n")
        results.append("/*\n")
        results.append(" * Security identifier indices for initial entities\n")
        results.append(" */\n")

        count = 0
        width = 56  # broken for old tools whitespace
        for s in self.sids:
            count += 1
            columnA = f"#define SECINITSID_{s.upper()} "
            columnA += "".join([" " for i in range(width - len(columnA))])
            results.append("%s%d\n" % (columnA, count))

        results.append("\n")
        columnA = "#define SECINITSID_NUM "
        columnA += "".join([" " for i in range(width - len(columnA))])
        results.append("%s%d\n" % (columnA, count))

        results.append("\n")
        results.append("#endif\n")
        return results

    def createInitialSidToStringH(self, mode=USERSPACE):
        """ """
        results = []
        results.append(self.autogen)
        results.append("static char *initial_sid_to_string[] =\n")
        results.append("{\n")
        results.append('    "null",\n')
        for s in self.sids:
            results.append(f'    "{s}",\n')
        results.append("};\n")
        results.append("\n")

        return results


def usage():
    """
    Returns the usage string.
    """
    print(
        f"Usage: {os.path.basename(sys.argv[0])} -a ACCESS_VECTORS -i INITIAL_SIDS -s SECURITY_CLASSES -o OUTPUT_DIRECTORY -k|-u [-w]",
        "",
        " -a --access_vectors\taccess vector definitions",
        " -i --initial_sids\tinitial sid definitions",
        " -s --security_classes\tsecurity class definitions",
        " -o --output\toutput directory for generated files",
        " -k --kernel\toutput mode set to kernel (kernel headers contain empty blocks for all classes specified with # userspace in the security_classes file)",
        " -u --user\toutput mode set to userspace",
        " -w --nowarnings\tsupresses output of warning messages",
    )


def main():
    # Parse command line args
    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            "a:i:s:o:kuwh",
            [
                "access_vectors=",
                "initial_sids=",
                "security_classes=",
                "output=",
                "kernel",
                "user",
                "nowarnings",
                "help",
            ],
        )
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    avec = None
    isid = None
    secc = None
    outd = None
    mode = None
    warn = True
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit(0)
        elif o in ("-a", "--access_vectors"):
            avec = a
        elif o in ("-i", "--initial_sids"):
            isid = a
        elif o in ("-s", "--security_classes"):
            secc = a
        elif o in ("-o", "--output"):
            outd = a
        elif o in ("-k", "--kernel"):
            if mode is not None:
                usage()
                sys.exit(2)
            mode = Flask.KERNEL
        elif o in ("-u", "--user"):
            if mode is not None:
                usage()
                sys.exit(2)
            mode = Flask.USERSPACE
        elif o in ("-w", "--nowarnings"):
            warn = False
        else:
            usage()
            sys.exit(2)

    if avec is None or isid is None or secc is None or outd is None:
        usage()
        sys.exit(2)

    try:
        f = Flask(warn)
        f.parseSids(isid)
        f.parseClasses(secc)
        f.parseVectors(avec)
        f.createHeaders(outd, mode)
    except Exception as e:
        print(e)
        sys.exit(2)


if __name__ == "__main__":
    main()
