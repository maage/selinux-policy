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
import xml
from collections.abc import Iterator
from typing import Any, Never, TextIO, TypeAlias
from xml.dom.minidom import Document, Element, parseString

from pyplate import TemplateManager, eval_data_t, tmpl_data_t, tmpl_param_t

namevalue_list_t: TypeAlias = list[tuple[str, str]]
menu_item_t: TypeAlias = tuple[str, list[tuple[str, str]]]
module_list_t: TypeAlias = dict[str, dict[str, str]]
sort_t: TypeAlias = tuple[str, Any]

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


def read_policy_xml(filename: str) -> xml.dom.minidom.Document:
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
        error(f"error opening {filename}")

    return doc


def gen_booleans_conf(
    doc: Document, file_name: str, namevalue_list: namevalue_list_t
) -> Iterator[str]:
    """
    Generates the booleans configuration file using the XML provided and the
    previous booleans configuration.
    """

    # tunables are currently implemented as booleans
    for elem_type in ("bool", "tunable"):
        for node in doc.getElementsByTagName(elem_type):
            if "name" not in node.attributes:
                error(f'{file_name} {elem_type} missing "name" attribute {node}')
            bool_name = node.attributes["name"].value
            bool_val = None
            if "dftval" in node.attributes:
                bool_val = node.attributes["dftval"].value
            desc = get_first_child_by_names(node, ["desc"])[0]

            if (bool_name, BOOL_ENABLED) in namevalue_list:
                bool_val = BOOL_ENABLED
            elif (bool_name, BOOL_DISABLED) in namevalue_list:
                bool_val = BOOL_DISABLED

            if bool_val is None:
                error(f"{file_name} {elem_type} {bool_name} missing value")

            if desc:
                bool_desc = format_txt_desc(desc)
                yield "#"
                for line in bool_desc.split("\n"):
                    yield f"# {line}" if line else "#"

            yield f"{bool_name} = {bool_val}"
            yield ""


def gen_module_conf(
    doc: Document, file_name: str, namevalue_list: namevalue_list_t
) -> Iterator[str]:
    """
    Generates the module configuration file using the XML provided and the
    previous module configuration.
    """
    # If file exists, preserve settings and modify if needed.
    # Otherwise, create it.

    yield from (
        "#",
        "# This file contains a listing of available modules.",
        "# To prevent a module from  being used in policy",
        f'# creation, set the module name to "{MOD_DISABLED}".',
        "#",
        f'# For monolithic policies, modules set to "{MOD_BASE}" and "{MOD_ENABLED}"',
        "# will be built into the policy.",
        "#",
        f'# For modular policies, modules set to "{MOD_BASE}" will be',
        f'# included in the base module.  "{MOD_ENABLED}" will be compiled',
        "# as individual loadable modules.",
        "#",
        "",
    )

    # For required in [True,False] is present so that the requiered modules
    # are at the top of the config file.
    for required in (True, False):
        for node in doc.getElementsByTagName("module"):
            mod_req = any(
                req.getAttribute("val") == "true"
                for req in node.getElementsByTagName("required")
            )

            # Skip if we arnt working on the right set of modules.
            if (mod_req and not required) or (not mod_req and required):
                continue

            mod_name = node.getAttribute("name")
            mod_layer = node.parentNode.getAttribute("name")

            if mod_name is None:
                error(f'{file_name} module missing "name" attribute')

            if mod_layer is not None:
                yield f"# Layer: {mod_layer}"
            yield f"# Module: {mod_name}"

            if required:
                yield "# Required in base"
            yield "#"

            desc = get_first_child_by_names(node, ["summary"])[0]
            if desc:
                for line in format_txt_desc(desc).split("\n"):
                    yield f"# {line}" if line else "#"

            # If the module is set as disabled.
            if (mod_name, MOD_DISABLED) in namevalue_list:
                yield f"{mod_name} = {MOD_DISABLED}"
            # If the module is set as enabled.
            elif (mod_name, MOD_ENABLED) in namevalue_list:
                yield f"{mod_name} = {MOD_ENABLED}"
            # If the module is set as base.
            # or
            # If the module is a new module.
            # Set the module to base if it is marked as required.
            elif ((mod_name, MOD_BASE) in namevalue_list) or mod_req:
                yield f"{mod_name} = {MOD_BASE}"
            # Set the module to enabled if it is not required.
            else:
                yield f"{mod_name} = {MOD_ENABLED}"
            yield ""


def get_conf(conf: TextIO) -> namevalue_list_t:
    """
    Returns a list of [name, value] pairs from a config file with the format
    name = value
    """

    namevalue_list: namevalue_list_t = []
    for i, line in enumerate(conf):
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        namevalue = line.split("=")
        if len(namevalue) != 2:
            warning(f'line {i:d}: "{line}" is not a valid line, skipping')
            continue

        nv = namevalue[0].strip(), namevalue[1].strip()
        if any(len(nve.split()) != 1 for nve in nv):
            warning(f'line {i:d}: "{line}" is not a valid line, skipping')
            continue

        namevalue_list.append(nv)

    return namevalue_list


def first_cmp_func(a: tuple[str, Any]) -> Any:
    """
    Return the first element to sort/compare on.
    """

    return a[0]


def int_cmp_func(a: dict[str, Any]) -> Any:
    """
    Return the interface name to sort/compare on.
    """

    return a["interface_name"]


def temp_cmp_func(a: dict[str, Any]) -> Any:
    """
    Return the template name to sort/compare on.
    """

    return a["template_name"]


def tun_cmp_func(a: dict[str, Any]) -> Any:
    """
    Return the tunable name to sort/compare on.
    """

    return a["tun_name"]


def bool_cmp_func(a: dict[str, Any]) -> Any:
    """
    Return the boolean name to sort/compare on.
    """

    return a["bool_name"]


def gen_doc_menu(
    mod_layer: str | None, module_list: module_list_t
) -> list[menu_item_t]:
    """
    Generates the HTML document menu.
    """

    menu = []
    for layer, value in module_list.items():
        cur_menu: menu_item_t = (layer, [])
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


def format_html_desc(node: Element) -> str:
    """
    Formats a XML node into a HTML format.
    """

    desc_buf = ""
    for desc in node.childNodes:
        if desc.nodeName == "#text":
            if desc.data != "":
                if desc.parentNode.nodeName != "p":
                    desc_buf += f"<p>{desc.data}</p>"
                else:
                    desc_buf += desc.data
        else:
            desc_buf += f"<{desc.nodeName}>{format_html_desc(desc)}</{desc.nodeName}>"

    return desc_buf


def format_txt_desc(node: Element) -> str:
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
                        desc_buf += f"\t -{li.firstChild.data}\n"

    return desc_buf.strip() + "\n"


def get_first_child_by_names(node: Element, names: list[str]) -> list[Element | None]:
    to_find = names.copy()
    results: list[Element | None] = [None] * len(names)
    for desc in node.childNodes:
        if (desc.nodeType != xml.dom.Node.ELEMENT_NODE) or (
            desc.tagName not in to_find
        ):
            continue
        idx = names.index(desc.tagName)
        results[idx] = desc
        to_find.remove(desc.tagName)
        if not to_find:
            break
    return results


def get_elem_summary_desc(node: Element) -> list[str]:
    results = []
    for desc in get_first_child_by_names(node, ["summary", "desc"]):
        # Some are missing
        results += ["" if desc is None else format_html_desc(desc)]
    return results


def get_layer_summary(doc: Document, mod_layer: str) -> str | None:
    for node in doc.getElementsByTagName("layer"):
        if node.getAttribute("name") == mod_layer:
            desc = get_first_child_by_names(node, ["summary"])[0]
            if desc:
                return format_html_desc(desc)
    return None


def gen_docs(doc: Document, working_dir: str, templatedir: str) -> None:
    """
    Generates all the documentation.
    """

    tm = TemplateManager()
    try:
        # get the template data ahead of time so we don't reopen them over and over
        for name, file_name in (
            ("body", "header.html"),
            ("int", "interface.html"),
            ("template", "template.html"),
            ("tun", "tunable.html"),
            ("bool", "boolean.html"),
            ("menu", "menu.html"),
            ("index", "module_list.html"),
            ("module", "module.html"),
            ("intlist", "int_list.html"),
            ("templist", "temp_list.html"),
            ("tunlist", "tun_list.html"),
            ("boollist", "bool_list.html"),
            ("gboollist", "global_bool_list.html"),
            ("gtunlist", "global_tun_list.html"),
        ):
            tm.set(name, os.path.join(templatedir, file_name))
    except OSError:
        error("Could not open templates")

    try:
        os.chdir(working_dir)
    except OSError:
        error("Could not chdir to target directory")

    # arg, i have to go through this dom tree ahead of time to build up the menus
    interface_buf: str | None
    body_args: eval_data_t
    module_list: module_list_t = {}
    for node in doc.getElementsByTagName("module"):
        mod_name = mod_layer = interface_buf = ""

        mod_name = node.getAttribute("name")
        mod_layer = node.parentNode.getAttribute("name")

        desc = get_first_child_by_names(node, ["summary"])[0]
        mod_summary = format_html_desc(desc) if desc else ""
        if mod_layer not in module_list:
            module_list[mod_layer] = {}

        module_list[mod_layer][mod_name] = mod_summary

    # generate index pages
    main_content_buf = ""
    for mod_layer in module_list:
        menu = gen_doc_menu(mod_layer, module_list)

        layer_summary = get_layer_summary(doc, mod_layer)

        menu_args = {
            "menulist": menu,
            "mod_layer": mod_layer,
            "layer_summary": layer_summary,
        }
        menu_tpl = tm.get("menu")
        menu_buf = menu_tpl.execute_string(menu_args)

        content_tpl = tm.get("index")
        content_buf = content_tpl.execute_string(menu_args)

        main_content_buf += content_buf

        body_args = {"menu": menu_buf, "content": content_buf}

        index_file = f"{mod_layer}.html"
        with open(index_file, "w") as index_fh:
            body_tpl = tm.get("body")
            body_tpl.execute(index_fh, body_args)

    menu = gen_doc_menu(None, module_list)
    menu_args = {"menulist": menu, "mod_layer": None}
    menu_tpl = tm.get("menu")
    menu_buf = menu_tpl.execute_string(menu_args)

    body_args = {"menu": menu_buf, "content": main_content_buf}

    index_file = "index.html"
    with open(index_file, "w") as index_fh:
        body_tpl = tm.get("body")
        body_tpl.execute(index_fh, body_args)

    # now generate the individual module pages
    all_interfaces: tmpl_data_t = []
    all_templates: tmpl_data_t = []
    all_tunables: tmpl_data_t = []
    all_booleans: tmpl_data_t = []
    for node in doc.getElementsByTagName("module"):
        tunable_buf: str | None
        template_buf: str | None
        boolean_buf: str | None
        interfaces: tmpl_data_t
        parameter: eval_data_t
        templates: tmpl_data_t
        booleans: tmpl_data_t
        tunables: tmpl_data_t

        mod_name = node.getAttribute("name")
        mod_layer = node.parentNode.getAttribute("name")
        mod_summary, mod_desc = get_elem_summary_desc(node)

        mod_req = None
        for req in node.getElementsByTagName("required"):
            if req.getAttribute("val") == "true":
                mod_req = True

        interfaces = []
        for interface in node.getElementsByTagName("interface"):
            interface_parameters: tmpl_param_t = []
            interface_summary, interface_desc = get_elem_summary_desc(interface)
            interface_name = interface.getAttribute("name")
            interface_line = interface.getAttribute("lineno")

            for args in interface.getElementsByTagName("param"):
                paramname = args.getAttribute("name")
                paramopt = "Yes" if args.getAttribute("optional") == "true" else "No"
                paramunused = "Yes" if args.getAttribute("unused") == "true" else "No"
                desc = get_first_child_by_names(args, ["summary"])[0]
                paramdesc = format_html_desc(desc) if desc else None
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
        interface_tpl = tm.get("int")
        interface_buf = interface_tpl.execute_string({"interfaces": interfaces})

        # now generate individual template pages
        templates = []
        for template in node.getElementsByTagName("template"):
            template_parameters: tmpl_param_t = []
            template_summary, template_desc = get_elem_summary_desc(template)
            template_name = template.getAttribute("name")
            template_line = template.getAttribute("lineno")

            for args in template.getElementsByTagName("param"):
                paramname = args.getAttribute("name")
                paramopt = "Yes" if args.getAttribute("optional") == "true" else "No"
                paramunused = "Yes" if args.getAttribute("unused") == "true" else "No"
                desc = get_first_child_by_names(args, ["summary"])[0]
                paramdesc = format_html_desc(desc) if desc else None
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
        template_tpl = tm.get("template")
        template_buf = template_tpl.execute_string({"templates": templates})

        # generate 'boolean' pages
        booleans = []
        for boolean in node.getElementsByTagName("bool"):
            boolean_name = boolean.getAttribute("name")
            boolean_dftval = boolean.getAttribute("dftval")
            desc = get_first_child_by_names(boolean, ["desc"])[0]
            boolean_desc = format_html_desc(desc) if desc else None
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
        boolean_tpl = tm.get("bool")
        boolean_buf = boolean_tpl.execute_string({"booleans": booleans})

        # generate 'tunable' pages
        tunables = []
        for tunable in node.getElementsByTagName("tunable"):
            tunable_name = tunable.getAttribute("name")
            tunable_dftval = tunable.getAttribute("dftval")
            desc = get_first_child_by_names(tunable, ["desc"])[0]
            tunable_desc = format_html_desc(desc) if desc else None
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
        tunable_tpl = tm.get("tun")
        tunable_buf = tunable_tpl.execute_string({"tunables": tunables})

        menu = gen_doc_menu(mod_layer, module_list)

        menu_tpl = tm.get("menu")
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
        assert interface_buf is not None
        if not interface_buf.strip():
            interface_buf = None
        assert template_buf is not None
        if not template_buf.strip():
            template_buf = None
        assert tunable_buf is not None
        if not tunable_buf.strip():
            tunable_buf = None
        assert boolean_buf is not None
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

        module_tpl = tm.get("module")
        module_buf = module_tpl.execute_string(module_args)

        body_args = {"menu": menu_buf, "content": module_buf}

        module_file = f"{mod_layer}_{mod_name}.html"
        with open(module_file, "w") as module_fh:
            body_tpl = tm.get("body")
            body_tpl.execute(module_fh, body_args)

    menu = gen_doc_menu(None, module_list)
    menu_args = {"menulist": menu, "mod_layer": None}
    menu_tpl = tm.get("menu")
    menu_buf = menu_tpl.execute_string(menu_args)

    # build the interface index
    all_interfaces.sort(key=int_cmp_func)
    interface_tpl = tm.get("intlist")
    interface_buf = interface_tpl.execute_string({"interfaces": all_interfaces})
    int_file = "interfaces.html"

    with open(int_file, "w") as int_fh:
        body_tpl = tm.get("body")
        body_args = {"menu": menu_buf, "content": interface_buf}
        body_tpl.execute(int_fh, body_args)

    # build the template index
    all_templates.sort(key=temp_cmp_func)
    template_tpl = tm.get("templist")
    template_buf = template_tpl.execute_string({"templates": all_templates})
    temp_file = "templates.html"
    with open(temp_file, "w") as temp_fh:
        body_tpl = tm.get("body")
        body_args = {"menu": menu_buf, "content": template_buf}
        body_tpl.execute(temp_fh, body_args)

    global_tun: tmpl_data_t
    global_bool: tmpl_data_t
    bool_args: eval_data_t

    # build the global tunable index
    global_tun = []
    for tunable in doc.getElementsByTagName("tunable"):
        if tunable.parentNode.nodeName != "policy":
            continue
        tunable_name = tunable.getAttribute("name")
        default_value = tunable.getAttribute("dftval")
        desc = get_first_child_by_names(tunable, ["desc"])[0]
        description = format_html_desc(desc) if desc else None
        global_tun.append(
            {"tun_name": tunable_name, "def_val": default_value, "desc": description}
        )
    global_tun.sort(key=tun_cmp_func)
    global_tun_tpl = tm.get("gtunlist")
    global_tun_buf = global_tun_tpl.execute_string({"tunables": global_tun})
    global_tun_file = "global_tunables.html"
    with open(global_tun_file, "w") as global_tun_fh:
        body_tpl = tm.get("body")
        body_args = {"menu": menu_buf, "content": global_tun_buf}
        body_tpl.execute(global_tun_fh, body_args)

    # build the tunable index
    all_tunables += global_tun
    all_tunables.sort(key=tun_cmp_func)
    tunable_tpl = tm.get("tunlist")
    tunable_buf = tunable_tpl.execute_string({"tunables": all_tunables})
    temp_file = "tunables.html"
    with open(temp_file, "w") as temp_fh:
        body_tpl = tm.get("body")
        body_args = {"menu": menu_buf, "content": tunable_buf}
        body_tpl.execute(temp_fh, body_args)

    # build the global boolean index
    global_bool = []
    for boolean in doc.getElementsByTagName("bool"):
        if boolean.parentNode.nodeName != "policy":
            continue
        bool_name = boolean.getAttribute("name")
        default_value = boolean.getAttribute("dftval")
        desc = get_first_child_by_names(boolean, ["desc"])[0]
        description = format_html_desc(desc) if desc else None
        global_bool.append(
            {"bool_name": bool_name, "def_val": default_value, "desc": description}
        )
    global_bool.sort(key=bool_cmp_func)
    global_bool_tpl = tm.get("gboollist")
    global_bool_args: eval_data_t = {"booleans": global_bool}
    global_bool_buf = global_bool_tpl.execute_string(global_bool_args)
    global_bool_file = "global_booleans.html"
    with open(global_bool_file, "w") as global_bool_fh:
        body_tpl = tm.get("body")
        body_args = {"menu": menu_buf, "content": global_bool_buf}
        body_tpl.execute(global_bool_fh, body_args)

    # build the boolean index
    all_booleans += global_bool
    all_booleans.sort(key=bool_cmp_func)
    boolean_tpl = tm.get("boollist")
    bool_args = {"booleans": all_booleans}
    boolean_buf = boolean_tpl.execute_string(bool_args)
    temp_file = "booleans.html"
    with open(temp_file, "w") as temp_fh:
        body_tpl = tm.get("body")
        body_args = {"menu": menu_buf, "content": boolean_buf}
        body_tpl.execute(temp_fh, body_args)


def error(msg: str) -> Never:
    """
    Print an error message and exit.
    """

    print(f"{sys.argv[0]} exiting for: {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


def warning(msg: str) -> None:
    """
    Print a warning message.
    """

    print(f"{sys.argv[0]} warning: {msg}", file=sys.stderr)


def usage() -> None:
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
def main() -> None:
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
    templatedir = "templates"
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
                print(
                    *(gen_booleans_conf(doc, xmlfile, namevalue_list)),
                    sep="",
                    file=conf,
                )
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
                print(
                    *(gen_module_conf(doc, xmlfile, namevalue_list)),
                    sep="\n",
                    file=conf,
                )
        except OSError:
            error("Could not open modules file for writing")

    if docsdir:
        gen_docs(doc, docsdir, templatedir)


if __name__ == "__main__":
    main()
