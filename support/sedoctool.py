#!/usr/bin/python

#  Author: Joshua Brindle <jbrindle@tresys.com>
#  Caleb Case <ccase@tresys.com>
#
# Copyright (C) 2005 - 2006 Tresys Technology, LLC
#      This program is free software; you can redistribute it and/or modify
#      it under the terms of the GNU General Public License as published by
#      the Free Software Foundation, version 2.

"""
    This module generates configuration files and documentation from the
    SELinux reference policy XML format.
"""

import getopt
import os
import sys
from xml.dom.minidom import parseString

import pyplate

# modules enabled and disabled values
MOD_BASE = "base"
MOD_ENABLED = "module"
MOD_DISABLED = "off"

# booleans enabled and disabled values
BOOL_ENABLED = "true"
BOOL_DISABLED = "false"

# tunables enabled and disabled values
TUN_ENABLED = "true"
TUN_DISABLED = "false"


def read_policy_xml(filename):
    """
    Takes in XML from a file and returns a parsed file.
    """

    try:
        with open(filename) as f:
            try:
                doc = parseString(f.read())  # noqa: S318
            except (TypeError, AttributeError):
                error("Error while parsing xml")
    except OSError:
        error("error opening " + filename)

    return doc


def gen_booleans_conf(doc, file_name, namevalue_list):
    """
    Generates the booleans configuration file using the XML provided and the
    previous booleans configuration.
    """

    for node in doc.getElementsByTagName("bool"):
        for desc in node.getElementsByTagName("desc"):
            bool_desc = format_txt_desc(desc)
        s = bool_desc.split("\n")
        file_name.write("#\n")
        for line in s:
            file_name.write(f"# {line}\n")

        bool_name = bool_val = None
        for name, value in node.attributes.items():
            if name == "name":
                bool_name = value
            elif name == "dftval":
                bool_val = value

            if [bool_name, BOOL_ENABLED] in namevalue_list:
                bool_val = BOOL_ENABLED
            elif [bool_name, BOOL_DISABLED] in namevalue_list:
                bool_val = BOOL_DISABLED

            if bool_name and bool_val:
                file_name.write(f"{bool_name} = {bool_val}\n\n")
                bool_name = bool_val = None

    # tunables are currently implemented as booleans
    for node in doc.getElementsByTagName("tunable"):
        for desc in node.getElementsByTagName("desc"):
            bool_desc = format_txt_desc(desc)
        s = bool_desc.split("\n")
        file_name.write("#\n")
        for line in s:
            file_name.write(f"# {line}\n")

        bool_name = bool_val = None
        for name, value in node.attributes.items():
            if name == "name":
                bool_name = value
            elif name == "dftval":
                bool_val = value

            if [bool_name, BOOL_ENABLED] in namevalue_list:
                bool_val = BOOL_ENABLED
            elif [bool_name, BOOL_DISABLED] in namevalue_list:
                bool_val = BOOL_DISABLED

            if bool_name and bool_val:
                file_name.write(f"{bool_name} = {bool_val}\n\n")
                bool_name = bool_val = None


def gen_module_conf(doc, file_name, namevalue_list):
    """
    Generates the module configuration file using the XML provided and the
    previous module configuration.
    """
    # If file exists, preserve settings and modify if needed.
    # Otherwise, create it.

    file_name.write("#\n# This file contains a listing of available modules.\n")
    file_name.write("# To prevent a module from  being used in policy\n")
    file_name.write(f'# creation, set the module name to "{MOD_DISABLED}".\n#\n')
    file_name.write(
        f'# For monolithic policies, modules set to "{MOD_BASE}" and "{MOD_ENABLED}"\n'
    )
    file_name.write("# will be built into the policy.\n#\n")
    file_name.write(f'# For modular policies, modules set to "{MOD_BASE}" will be\n')
    file_name.write(
        f'# included in the base module.  "{MOD_ENABLED}" will be compiled\n'
    )
    file_name.write("# as individual loadable modules.\n#\n\n")

    # For required in [True,False] is present so that the requiered modules
    # are at the top of the config file.
    for required in [True, False]:
        for node in doc.getElementsByTagName("module"):
            mod_req = False
            for req in node.getElementsByTagName("required"):
                if req.getAttribute("val") == "true":
                    mod_req = True

            # Skip if we arnt working on the right set of modules.
            if mod_req and not required or not mod_req and required:
                continue

            mod_name = mod_layer = None

            mod_name = node.getAttribute("name")
            mod_layer = node.parentNode.getAttribute("name")

            if mod_name and mod_layer:
                file_name.write(f"# Layer: {mod_layer}\n# Module: {mod_name}\n")
                if required:
                    file_name.write("# Required in base\n")
                file_name.write("#\n")

            for desc in node.getElementsByTagName("summary"):
                if desc.parentNode != node:
                    continue
                s = format_txt_desc(desc).split("\n")
                for line in s:
                    file_name.write(f"# {line}\n")

                # If the module is set as disabled.
                if [mod_name, MOD_DISABLED] in namevalue_list:
                    file_name.write(f"{mod_name} = {MOD_DISABLED}\n\n")
                # If the module is set as enabled.
                elif [mod_name, MOD_ENABLED] in namevalue_list:
                    file_name.write(f"{mod_name} = {MOD_ENABLED}\n\n")
                # If the module is set as base.
                # or
                # If the module is a new module.
                # Set the module to base if it is marked as required.
                elif ([mod_name, MOD_BASE] in namevalue_list) or mod_req:
                    file_name.write(f"{mod_name} = {MOD_BASE}\n\n")
                # Set the module to enabled if it is not required.
                else:
                    file_name.write(f"{mod_name} = {MOD_ENABLED}\n\n")


def get_conf(conf):
    """
    Returns a list of [name, value] pairs from a config file with the format
    name = value
    """

    conf_lines = conf.readlines()

    namevalue_list = []
    for i, line in enumerate(conf_lines):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        namevalue = line.split("=")
        if len(namevalue) != 2:
            warning(f'line {i:d}: "{line}" is not a valid line, skipping')
            continue

        namevalue[0] = namevalue[0].strip()
        if len(namevalue[0].split()) > 1:
            warning(f'line {i:d}: "{line}" is not a valid line, skipping')
            continue

        namevalue[1] = namevalue[1].strip()
        if len(namevalue[1].split()) > 1:
            warning(f'line {i:d}: "{line}" is not a valid line, skipping')
            continue

        namevalue_list.append(namevalue)

    return namevalue_list


def first_cmp_func(a):
    """
    Return the first element to sort/compare on.
    """

    return a[0]


def int_cmp_func(a):
    """
    Return the interface name to sort/compare on.
    """

    return a["interface_name"]


def temp_cmp_func(a):
    """
    Return the template name to sort/compare on.
    """

    return a["template_name"]


def tun_cmp_func(a):
    """
    Return the tunable name to sort/compare on.
    """

    return a["tun_name"]


def bool_cmp_func(a):
    """
    Return the boolean name to sort/compare on.
    """

    return a["bool_name"]


def gen_doc_menu(mod_layer, module_list):
    """
    Generates the HTML document menu.
    """

    menu = []
    for layer, value in module_list.items():
        cur_menu = (layer, [])
        menu.append(cur_menu)
        if layer != mod_layer and mod_layer is not None:
            continue
        # we are in our layer so fill in the other modules or we want them all
        for mod, desc in value.items():
            cur_menu[1].append((mod, desc))

    menu.sort(key=first_cmp_func)
    for x in menu:
        x[1].sort(key=first_cmp_func)
    return menu


def format_html_desc(node):
    """
    Formats a XML node into a HTML format.
    """

    desc_buf = ""
    for desc in node.childNodes:
        if desc.nodeName == "#text":
            if desc.data != "":
                if desc.parentNode.nodeName != "p":
                    desc_buf += "<p>" + desc.data + "</p>"
                else:
                    desc_buf += desc.data
        else:
            desc_buf += (
                "<"
                + desc.nodeName
                + ">"
                + format_html_desc(desc)
                + "</"
                + desc.nodeName
                + ">"
            )

    return desc_buf


def format_txt_desc(node):
    """
    Formats a XML node into a plain text format.
    """

    desc_buf = ""
    for desc in node.childNodes:
        if desc.nodeName == "#text":
            desc_buf += desc.data + "\n"
        elif desc.nodeName == "p":
            desc_buf += desc.firstChild.data + "\n"
            for chld in desc.childNodes:
                if chld.nodeName == "ul":
                    desc_buf += "\n"
                    for li in chld.getElementsByTagName("li"):
                        desc_buf += "\t -" + li.firstChild.data + "\n"

    return desc_buf.strip() + "\n"


def gen_docs(doc, working_dir, templatedir):
    """
    Generates all the documentation.
    """

    try:
        # get the template data ahead of time so we don't reopen them over and over
        with open(templatedir + "/header.html") as f:
            bodydata = f.read()
        with open(templatedir + "/interface.html") as f:
            intdata = f.read()
        with open(templatedir + "/template.html") as f:
            templatedata = f.read()
        with open(templatedir + "/tunable.html") as f:
            tundata = f.read()
        with open(templatedir + "/boolean.html") as f:
            booldata = f.read()
        with open(templatedir + "/menu.html") as f:
            menudata = f.read()
        with open(templatedir + "/module_list.html") as f:
            indexdata = f.read()
        with open(templatedir + "/module.html") as f:
            moduledata = f.read()
        with open(templatedir + "/int_list.html") as f:
            intlistdata = f.read()
        with open(templatedir + "/temp_list.html") as f:
            templistdata = f.read()
        with open(templatedir + "/tun_list.html") as f:
            tunlistdata = f.read()
        with open(templatedir + "/bool_list.html") as f:
            boollistdata = f.read()
        with open(templatedir + "/global_bool_list.html") as f:
            gboollistdata = f.read()
        with open(templatedir + "/global_tun_list.html") as f:
            gtunlistdata = f.read()
    except OSError:
        error("Could not open templates")

    try:
        os.chdir(working_dir)
    except OSError:
        error("Could not chdir to target directory")

    # arg, i have to go through this dom tree ahead of time to build up the menus
    module_list = {}
    for node in doc.getElementsByTagName("module"):
        mod_name = mod_layer = interface_buf = ""

        mod_name = node.getAttribute("name")
        mod_layer = node.parentNode.getAttribute("name")

        for desc in node.getElementsByTagName("summary"):
            if desc.parentNode == node and desc:
                mod_summary = format_html_desc(desc)
        if mod_layer not in module_list:
            module_list[mod_layer] = {}

        module_list[mod_layer][mod_name] = mod_summary

    # generate index pages
    main_content_buf = ""
    for mod_layer in module_list:
        menu = gen_doc_menu(mod_layer, module_list)

        layer_summary = None
        for desc in doc.getElementsByTagName("summary"):
            if desc.parentNode.getAttribute("name") == mod_layer:
                layer_summary = format_html_desc(desc)

        menu_args = {
            "menulist": menu,
            "mod_layer": mod_layer,
            "layer_summary": layer_summary,
        }
        menu_tpl = pyplate.Template(menudata)
        menu_buf = menu_tpl.execute_string(menu_args)

        content_tpl = pyplate.Template(indexdata)
        content_buf = content_tpl.execute_string(menu_args)

        main_content_buf += content_buf

        body_args = {"menu": menu_buf, "content": content_buf}

        index_file = mod_layer + ".html"
        with open(index_file, "w") as index_fh:
            body_tpl = pyplate.Template(bodydata)
            body_tpl.execute(index_fh, body_args)

    menu = gen_doc_menu(None, module_list)
    menu_args = {"menulist": menu, "mod_layer": None}
    menu_tpl = pyplate.Template(menudata)
    menu_buf = menu_tpl.execute_string(menu_args)

    body_args = {"menu": menu_buf, "content": main_content_buf}

    index_file = "index.html"
    with open(index_file, "w") as index_fh:
        body_tpl = pyplate.Template(bodydata)
        body_tpl.execute(index_fh, body_args)

    # now generate the individual module pages
    all_interfaces = []
    all_templates = []
    all_tunables = []
    all_booleans = []
    for node in doc.getElementsByTagName("module"):
        mod_name = mod_layer = mod_desc = interface_buf = ""

        mod_name = node.getAttribute("name")
        mod_layer = node.parentNode.getAttribute("name")

        mod_req = None
        for req in node.getElementsByTagName("required"):
            if req.getAttribute("val") == "true":
                mod_req = True

        for desc in node.getElementsByTagName("summary"):
            if desc.parentNode == node:
                mod_summary = format_html_desc(desc)
        for desc in node.getElementsByTagName("desc"):
            if desc.parentNode == node:
                mod_desc = format_html_desc(desc)

        interfaces = []
        for interface in node.getElementsByTagName("interface"):
            interface_parameters = []
            interface_desc = interface_summary = None
            interface_name = interface.getAttribute("name")
            interface_line = interface.getAttribute("lineno")
            for desc in interface.childNodes:
                if desc.nodeName == "desc":
                    interface_desc = format_html_desc(desc)
                elif desc.nodeName == "summary":
                    interface_summary = format_html_desc(desc)

            for args in interface.getElementsByTagName("param"):
                for desc in args.getElementsByTagName("summary"):
                    paramdesc = format_html_desc(desc)
                paramname = args.getAttribute("name")
                paramopt = "Yes" if args.getAttribute("optional") == "true" else "No"
                paramunused = "Yes" if args.getAttribute("unused") == "true" else "No"
                parameter = {
                    "name": paramname,
                    "desc": paramdesc,
                    "optional": paramopt,
                    "unused": paramunused,
                }
                interface_parameters.append(parameter)
            interfaces.append(
                {
                    "interface_name": interface_name,
                    "interface_line": interface_line,
                    "interface_summary": interface_summary,
                    "interface_desc": interface_desc,
                    "interface_parameters": interface_parameters,
                }
            )
            # all_interfaces is for the main interface index with all interfaces
            all_interfaces.append(
                {
                    "interface_name": interface_name,
                    "interface_line": interface_line,
                    "interface_summary": interface_summary,
                    "interface_desc": interface_desc,
                    "interface_parameters": interface_parameters,
                    "mod_name": mod_name,
                    "mod_layer": mod_layer,
                }
            )
        interfaces.sort(key=int_cmp_func)
        interface_tpl = pyplate.Template(intdata)
        interface_buf = interface_tpl.execute_string({"interfaces": interfaces})

        # now generate individual template pages
        templates = []
        for template in node.getElementsByTagName("template"):
            template_parameters = []
            template_desc = template_summary = None
            template_name = template.getAttribute("name")
            template_line = template.getAttribute("lineno")
            for desc in template.childNodes:
                if desc.nodeName == "desc":
                    template_desc = format_html_desc(desc)
                elif desc.nodeName == "summary":
                    template_summary = format_html_desc(desc)

            for args in template.getElementsByTagName("param"):
                for desc in args.getElementsByTagName("summary"):
                    paramdesc = format_html_desc(desc)
                paramname = args.getAttribute("name")
                paramopt = "Yes" if args.getAttribute("optional") == "true" else "No"
                paramunused = "Yes" if args.getAttribute("unused") == "true" else "No"
                parameter = {
                    "name": paramname,
                    "desc": paramdesc,
                    "optional": paramopt,
                    "unused": paramunused,
                }
                template_parameters.append(parameter)
            templates.append(
                {
                    "template_name": template_name,
                    "template_line": template_line,
                    "template_summary": template_summary,
                    "template_desc": template_desc,
                    "template_parameters": template_parameters,
                }
            )
            # all_templates is for the main interface index with all templates
            all_templates.append(
                {
                    "template_name": template_name,
                    "template_line": template_line,
                    "template_summary": template_summary,
                    "template_desc": template_desc,
                    "template_parameters": template_parameters,
                    "mod_name": mod_name,
                    "mod_layer": mod_layer,
                }
            )

        templates.sort(key=temp_cmp_func)
        template_tpl = pyplate.Template(templatedata)
        template_buf = template_tpl.execute_string({"templates": templates})

        # generate 'boolean' pages
        booleans = []
        for boolean in node.getElementsByTagName("bool"):
            boolean_desc = None
            boolean_name = boolean.getAttribute("name")
            boolean_dftval = boolean.getAttribute("dftval")
            for desc in boolean.childNodes:
                if desc.nodeName == "desc":
                    boolean_desc = format_html_desc(desc)

            booleans.append(
                {
                    "bool_name": boolean_name,
                    "desc": boolean_desc,
                    "def_val": boolean_dftval,
                }
            )
            # all_booleans is for the main boolean index with all booleans
            all_booleans.append(
                {
                    "bool_name": boolean_name,
                    "desc": boolean_desc,
                    "def_val": boolean_dftval,
                    "mod_name": mod_name,
                    "mod_layer": mod_layer,
                }
            )
        booleans.sort(key=bool_cmp_func)
        boolean_tpl = pyplate.Template(booldata)
        boolean_buf = boolean_tpl.execute_string({"booleans": booleans})

        # generate 'tunable' pages
        tunables = []
        for tunable in node.getElementsByTagName("tunable"):
            tunable_desc = None
            tunable_name = tunable.getAttribute("name")
            tunable_dftval = tunable.getAttribute("dftval")
            for desc in tunable.childNodes:
                if desc.nodeName == "desc":
                    tunable_desc = format_html_desc(desc)

            tunables.append(
                {
                    "tun_name": tunable_name,
                    "desc": tunable_desc,
                    "def_val": tunable_dftval,
                }
            )
            # all_tunables is for the main tunable index with all tunables
            all_tunables.append(
                {
                    "tun_name": tunable_name,
                    "desc": tunable_desc,
                    "def_val": tunable_dftval,
                    "mod_name": mod_name,
                    "mod_layer": mod_layer,
                }
            )
        tunables.sort(key=tun_cmp_func)
        tunable_tpl = pyplate.Template(tundata)
        tunable_buf = tunable_tpl.execute_string({"tunables": tunables})

        menu = gen_doc_menu(mod_layer, module_list)

        menu_tpl = pyplate.Template(menudata)
        menu_buf = menu_tpl.execute_string({"menulist": menu})

        # pyplate's execute_string gives us a line of whitespace in
        # template_buf or interface_buf if there are no interfaces or
        # templates for this module. This is problematic because the
        # HTML templates use a conditional if on interface_buf or
        # template_buf being 'None' to decide if the "Template:" or
        # "Interface:" headers need to be printed in the module pages.
        # This detects if either of these are just whitespace, and sets
        # their values to 'None' so that when applying it to the
        # templates, they are properly recognized as not existing.
        if not interface_buf.strip():
            interface_buf = None
        if not template_buf.strip():
            template_buf = None
        if not tunable_buf.strip():
            tunable_buf = None
        if not boolean_buf.strip():
            boolean_buf = None

        module_args = {
            "mod_layer": mod_layer,
            "mod_name": mod_name,
            "mod_summary": mod_summary,
            "mod_desc": mod_desc,
            "mod_req": mod_req,
            "interfaces": interface_buf,
            "templates": template_buf,
            "tunables": tunable_buf,
            "booleans": boolean_buf,
        }

        module_tpl = pyplate.Template(moduledata)
        module_buf = module_tpl.execute_string(module_args)

        body_args = {"menu": menu_buf, "content": module_buf}

        module_file = mod_layer + "_" + mod_name + ".html"
        with open(module_file, "w") as module_fh:
            body_tpl = pyplate.Template(bodydata)
            body_tpl.execute(module_fh, body_args)

    menu = gen_doc_menu(None, module_list)
    menu_args = {"menulist": menu, "mod_layer": None}
    menu_tpl = pyplate.Template(menudata)
    menu_buf = menu_tpl.execute_string(menu_args)

    # build the interface index
    all_interfaces.sort(key=int_cmp_func)
    interface_tpl = pyplate.Template(intlistdata)
    interface_buf = interface_tpl.execute_string({"interfaces": all_interfaces})
    int_file = "interfaces.html"

    with open(int_file, "w") as int_fh:
        body_tpl = pyplate.Template(bodydata)
        body_args = {"menu": menu_buf, "content": interface_buf}
        body_tpl.execute(int_fh, body_args)

    # build the template index
    all_templates.sort(key=temp_cmp_func)
    template_tpl = pyplate.Template(templistdata)
    template_buf = template_tpl.execute_string({"templates": all_templates})
    temp_file = "templates.html"
    with open(temp_file, "w") as temp_fh:
        body_tpl = pyplate.Template(bodydata)
        body_args = {"menu": menu_buf, "content": template_buf}
        body_tpl.execute(temp_fh, body_args)

    # build the global tunable index
    global_tun = []
    for tunable in doc.getElementsByTagName("tunable"):
        if tunable.parentNode.nodeName == "policy":
            tunable_name = tunable.getAttribute("name")
            default_value = tunable.getAttribute("dftval")
            for desc in tunable.getElementsByTagName("desc"):
                description = format_html_desc(desc)
            global_tun.append(
                {
                    "tun_name": tunable_name,
                    "def_val": default_value,
                    "desc": description,
                }
            )
    global_tun.sort(key=tun_cmp_func)
    global_tun_tpl = pyplate.Template(gtunlistdata)
    global_tun_buf = global_tun_tpl.execute_string({"tunables": global_tun})
    global_tun_file = "global_tunables.html"
    with open(global_tun_file, "w") as global_tun_fh:
        body_tpl = pyplate.Template(bodydata)
        body_args = {"menu": menu_buf, "content": global_tun_buf}
        body_tpl.execute(global_tun_fh, body_args)

    # build the tunable index
    all_tunables = all_tunables + global_tun
    all_tunables.sort(key=tun_cmp_func)
    tunable_tpl = pyplate.Template(tunlistdata)
    tunable_buf = tunable_tpl.execute_string({"tunables": all_tunables})
    temp_file = "tunables.html"
    with open(temp_file, "w") as temp_fh:
        body_tpl = pyplate.Template(bodydata)
        body_args = {"menu": menu_buf, "content": tunable_buf}
        body_tpl.execute(temp_fh, body_args)

    # build the global boolean index
    global_bool = []
    for boolean in doc.getElementsByTagName("bool"):
        if boolean.parentNode.nodeName == "policy":
            bool_name = boolean.getAttribute("name")
            default_value = boolean.getAttribute("dftval")
            for desc in boolean.getElementsByTagName("desc"):
                description = format_html_desc(desc)
            global_bool.append(
                {"bool_name": bool_name, "def_val": default_value, "desc": description}
            )
    global_bool.sort(key=bool_cmp_func)
    global_bool_tpl = pyplate.Template(gboollistdata)
    global_bool_buf = global_bool_tpl.execute_string({"booleans": global_bool})
    global_bool_file = "global_booleans.html"
    with open(global_bool_file, "w") as global_bool_fh:
        body_tpl = pyplate.Template(bodydata)
        body_args = {"menu": menu_buf, "content": global_bool_buf}
        body_tpl.execute(global_bool_fh, body_args)

    # build the boolean index
    all_booleans = all_booleans + global_bool
    all_booleans.sort(key=bool_cmp_func)
    boolean_tpl = pyplate.Template(boollistdata)
    boolean_buf = boolean_tpl.execute_string({"booleans": all_booleans})
    temp_file = "booleans.html"
    with open(temp_file, "w") as temp_fh:
        body_tpl = pyplate.Template(bodydata)
        body_args = {"menu": menu_buf, "content": boolean_buf}
        body_tpl.execute(temp_fh, body_args)


def error(msg):
    """
    Print an error message and exit.
    """

    print(f"{sys.argv[0]} exiting for: {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


def warning(msg):
    """
    Print a warning message.
    """

    print(f"{sys.argv[0]} warning: {msg}", file=sys.stderr)


def usage():
    """
    Describes the proper usage of this tool.
    """

    print(
        f"{sys.argv[0]} [-tmdT] -x <xmlfile>",
        "",
        "Options:",
        "-b --booleans	<file>		--	write boolean config to <file>",
        "-m --modules <file>		--	write module config to <file>",
        "-d --docs <dir>		--	write interface documentation to <dir>",
        "-x --xml <file>		--	filename to read xml data from",
        "-T --templates <dir>		--	template directory for documents",
    )


# MAIN PROGRAM
def main():
    try:
        opts, _args = getopt.getopt(
            sys.argv[1:],
            "b:m:d:x:T:",
            ["booleans", "modules", "docs", "xml", "templates"],
        )
    except getopt.GetoptError:
        usage()
        sys.exit(1)

    booleans = modules = docsdir = None
    templatedir = "templates/"
    xmlfile = "policy.xml"

    for opt, val in opts:
        if opt in ("-b", "--booleans"):
            booleans = val
        if opt in ("-m", "--modules"):
            modules = val
        if opt in ("-d", "--docs"):
            docsdir = val
        if opt in ("-x", "--xml"):
            xmlfile = val
        if opt in ("-T", "--templates"):
            templatedir = val

    doc = read_policy_xml(xmlfile)

    if booleans:
        namevalue_list = []
        if os.path.exists(booleans):
            try:
                with open(booleans) as conf:
                    namevalue_list = get_conf(conf)
            except OSError:
                error("Could not open booleans file for reading")

        try:
            with open(booleans, "w") as conf:
                gen_booleans_conf(doc, conf, namevalue_list)
        except OSError:
            error("Could not open booleans file for writing")

    if modules:
        namevalue_list = []
        if os.path.exists(modules):
            try:
                with open(modules) as conf:
                    namevalue_list = get_conf(conf)
            except OSError:
                error("Could not open modules file for reading")

        try:
            with open(modules, "w") as conf:
                gen_module_conf(doc, conf, namevalue_list)
        except OSError:
            error("Could not open modules file for writing")

    if docsdir:
        gen_docs(doc, docsdir, templatedir)


if __name__ == "__main__":
    main()
