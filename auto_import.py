import sublime, sublime_plugin
import os
import re
import textwrap

class ImportStyle(object):
    COMPONENT = 'component'
    ABSOLUTE = 'absolute'
    RELATIVE = 'relative'


def build_import_statement(symbol, path, root_path=None, style=ImportStyle.COMPONENT):
    """
    Builds an import statement from a symbol and a path

    :Parameters:
        `symbol`
            The identifier to be imported, e.g. x in
                from a.b.c import x

        `path`
            The path to the file containing the identifier, e.g.
                /a/b/c/test.py

        `root_path`
            The root directory to start the import from, e.g.
                root_path = "/a/b/" becomes
                from c import x

        `style`
            "component" (default)
                from x.y.z import a

            "absolute"
                import x.y.z.a

            "relative" (todo)
                from ..y.z import a

    .. todo::
        Relative imports
        smarter root checking (PYTHONPATH?)
        use os methods for path manipulation?
        Do I care about / vs \ ?

    """
    if root_path is None:
        root_path = '/'
    root_path = root_path.replace('.', '/')  # Support providing root_path as 'x.y.z'
    if not root_path.startswith('/'):
        root_path = '/' + root_path
    if not path.startswith('/'):
        path = '/' + path

    if path.startswith(root_path):
        path = path[len(root_path):]
    if path.endswith('.py'):
        path = path[:-len('.py')]
    if path.endswith('__init__'):
        path = path[:-len('__init__')]

    import_path = path.replace('/', '.').strip('.')

    if style == ImportStyle.COMPONENT:
        template = "from {module} import {symbol}"
    elif style == ImportStyle.ABSOLUTE:
        template = "import {module}.{symbol}"
    elif style == ImportStyle.RELATIVE:
        return  # TODO
    else:
        return

    return template.format(module=import_path, symbol=symbol)


# Regex for matching the drive letter in a Windows path
WINDOWS_DRIVE_LETTER_RE = re.compile(r'^([A-Z]):\\')
# Regex for matching the drive letter in the Sublime symbol index paths
UNIX_DRIVE_LETTER_RE = re.compile(r'^/([A-Z])/')

# Import on the first line that doesn't match this
# This is a guess as to where imports stop and code starts
IMPORT_CHECK_SKIP_RE = re.compile(r"""
    ^
    \s |        # Whitespace
    [#'"] |     # comments
    __ |        # __author__ etc
    import |    # import statements
    from |
    try |       # try / except Import Error
    except |
    $
""", re.X)

# These are valid lines to insert an import after
IMPORT_CHECK_VALID_RE = re.compile(r"""
    ^
    __ |        # __author__ etc
    import |    # import statements
    from
""", re.X)


# True if the line starts with a space or tab
INDENT_RE = re.compile(r"^[ \t]")

import_wrapper = textwrap.TextWrapper(
    width=76,
    subsequent_indent=' '*4,
    break_long_words=False,
)


def is_block_comment(line):
    """ Entering/exiting a block comment """
    line = line.strip()
    if line == '"""' or (line.startswith('"""') and not line.endswith('"""')):
        return True
    if line == "'''" or (line.startswith("'''") and not line.endswith("'''")):
        return True
    return False

def split_import_components(import_statement):
    """
    Given a (multi-line) import statement, return the base and components

        from x.y import a, b, c

        ->

        ('x.y', ['a', 'b', 'c'])
    """
    left, right = import_statement.split('import')
    right = right \
        .replace('(', '') \
        .replace(')', '') \
        .replace('\\', '')

    base = left.replace('from', '').strip()

    components = [
        component.strip()
        for component
        in right.split(',')
        if component
    ]
    return base, components

class InsertPythonAutoImportCommand(sublime_plugin.TextCommand):

    @property
    def settings(self):
        return sublime.load_settings("PythonAutoImport.sublime-settings")

    @property
    def root_path(self):
        return self.settings.get('root_path', '/')

    @property
    def scroll_to_import(self):
        return self.settings.get('scroll_to_import', True)

    def paths_equal(self, symbol_path, view_path):
        """
        Compares a path from the symbol index to a path returned by View.file_name()

        Returns `True` if they are the same path

        `symbol_path`
            A path returned by Window.lookup_symbol_in_*

        `view_path`
            A path returned by View.file_name()

        Sublime seems to store paths in the symbol index in Unix format
        ("/c/test/") even on Windows platforms ("C:\\test\\")

        This method tries to compare them by converting them to the same format
        """

        # Try to detect a Windows style path in the view_path
        if WINDOWS_DRIVE_LETTER_RE.match(view_path):
            # Extract the drive letter from the symbol path, and reformat
            # the symbol path as a windows path
            symbol_path = UNIX_DRIVE_LETTER_RE.sub(r"\g<1>:\\", symbol_path)
            symbol_path = symbol_path.replace('/', '\\')

        return symbol_path == view_path

    def insert_import(self, edit, entry, symbol, style=None):
        """
        Adds an import statement at the top of the current file

        `entry`
            A result from Window.lookup_symbol_in_*

        `symbol`
            The name of the symbol we are importing

        `style`
            See :func:`build_import_statement`
        """
        full_path, relative_path, offset = entry
        file_path = self.view.file_name()

        # Make sure they're not trying to import from the same file
        if self.paths_equal(full_path, file_path):
            return sublime.status_message('AutoPythonImport:  The symbol you are trying to import is defined in this file')

        import_statement = build_import_statement(symbol, relative_path, root_path=self.root_path, style=style)
        if not import_statement:
            return sublime.status_message('AutoPythonImport:  There was a problem constructing the import statement')

        import_base, _ = split_import_components(import_statement)

        # TODO Append to existing import at top of file

        """
            Try to find an existing import for this statement

            If not found, try to find the first real line of code, so we can
            insert the import above that (but below existing imports)
        """
        all_region = sublime.Region(0, self.view.size())

        insert_at = None
        in_block = False  # Whether we're in a block comment
        file_top = True   # Whether we're on the first statement in the file
        for region in self.view.lines(all_region):
            line = self.view.substr(region)

            if line.strip() == import_statement:
                return sublime.status_message('AutoPythonImport:  This import statement already exists')

            # Default to top of file
            if not insert_at:
                insert_at = region

            # Detect if we're entering or exiting a block comment
            if is_block_comment(line):
                in_block = not in_block

            # We care if we're looking at the very first statement in the file
            # (always add import below it)
            if not in_block and not line.startswith('#'):
                file_top = False

            # Look for an existing component import statement that we can add to
            if style == ImportStyle.COMPONENT:
                if line.strip().startswith("from " + import_base + " import"):
                    existing_import = line

                    # Check if this is a line-continuation import
                    existing_import_line_region = region.end() + 1
                    existing_import_region = sublime.Region(existing_import_line_region, self.view.size())
                    existing_import_lines = self.view.lines(existing_import_region)
                    for existing_import_line_region in existing_import_lines:
                        existing_import_line = self.view.substr(existing_import_line_region)
                        if not INDENT_RE.match(existing_import_line):
                            break
                        existing_import += existing_import_line

                    existing_import_base, existing_import_components = \
                        split_import_components(existing_import)

                    if symbol in existing_import_components:
                        return sublime.status_message('AutoPythonImport:  This import statement already exists')

                    new_import_statement = "from {base} import {components}".format(
                        base=existing_import_base,
                        components=', '.join(existing_import_components + [symbol]),
                    )

                    wrapped_import_statement = import_wrapper.wrap(new_import_statement)
                    final_import_statement = '\n'.join(wrapped_import_statement)

                    # Add parentheses \ slashes if we had to wrap the import statement
                    if len(wrapped_import_statement) > 1:
                        if '\\' in existing_import:
                            final_import_statement = final_import_statement.replace('\n', ' \\\n')
                        else:
                            final_import_statement = final_import_statement.replace('import ', 'import (') + ')'

                    replace_import_region = sublime.Region(region.begin(), existing_import_line_region.begin() - 1)
                    if self.scroll_to_import:
                        self.view.show(replace_import_region)
                        self.view.sel().clear()
                        self.view.sel().add(replace_import_region.end())

                    self.view.replace(edit, replace_import_region, final_import_statement)
                    return sublime.status_message('AutoPythonImport:  Appended {}'.format(symbol))

            if in_block or IMPORT_CHECK_SKIP_RE.match(line):
                if not in_block:
                    # Check if we can import below this line
                    # We don't want to import below comments,
                    # unless it is the first line in the file
                    if IMPORT_CHECK_VALID_RE.match(line) or file_top:
                        insert_at = region
                continue

            # Found line of "real" code
            break

        if self.scroll_to_import:
            self.view.show(insert_at.begin())
            self.view.sel().clear()
            self.view.sel().add(insert_at.end())
        self.view.replace(edit, insert_at, self.view.substr(insert_at) + '\n' + import_statement)

        return sublime.status_message('AutoPythonImport:  Added {}'.format(import_statement))

    def run(self, edit, entry, symbol, style):
        self.insert_import(edit, entry, symbol, style)

class PythonAutoImportCommand(sublime_plugin.TextCommand):

    def select_entry(self, locations, idx, symbol, style):
        if idx >= 0:
            self.view.run_command(
                'insert_python_auto_import',
                {
                    "entry": locations[idx],
                    "symbol": symbol,
                    "style": style,
                }
            )
        self.view.window().focus_view(self.view)

    def highlight_entry(self, locations, idx):
        fname, display_fname, rowcol = locations[idx]
        row, col = rowcol

        self.view.window().open_file(fname + ":" + str(row) + ":" + str(col),
            sublime.TRANSIENT | sublime.ENCODED_POSITION)

    def format_location(self, l):
        fname, display_fname, rowcol = l
        row, col = rowcol

        return display_fname + ":" + str(row)

    def lookup_symbol(self, symbol):
        index_locations = self.view.window().lookup_symbol_in_index(symbol)
        open_file_locations = self.view.window().lookup_symbol_in_open_files(symbol)
        open_file_paths = set([l[0] for l in open_file_locations])

        # Combine the two lists, overriding results in the index with results
        # from open files, while trying to preserve the order of the files in
        # the index.
        locations = []
        ofl_ignore = set([self.view.file_name()])
        for l in index_locations:
            if l[0] in open_file_paths:
                if l[0] not in ofl_ignore:
                    for ofl in open_file_locations:
                        if l[0] == ofl[0]:
                            locations.append(ofl)
                            ofl_ignore.add(ofl[0])
            else:
                locations.append(l)

        for ofl in open_file_locations:
            if ofl[0] not in ofl_ignore:
                locations.append(ofl)

        return locations

    def run(self, edit, symbol=None, style=None):
        self.edit = edit
        if style is None:
            style = ImportStyle.COMPONENT

        pt = self.view.sel()[0]

        if symbol is not None:
            locations = self.lookup_symbol(symbol)

        else:
            symbol = self.view.substr(self.view.expand_by_class(pt,
                sublime.CLASS_WORD_START | sublime.CLASS_WORD_END,
                "[]{}()<>:."))
            locations = self.lookup_symbol(symbol)

            if len(locations) == 0:
                symbol = self.view.substr(self.view.word(pt))
                locations = self.lookup_symbol(symbol)

        if len(locations) == 0:
            sublime.status_message("Unable to find " + symbol)
        elif len(locations) == 1:
            self.view.run_command(
                'insert_python_auto_import',
                {
                    "entry": locations[0],
                    "symbol": symbol,
                    "style": style,
                }
            )
        else:
            self.view.window().show_quick_panel(
                [self.format_location(l) for l in locations],
                lambda x: self.select_entry(locations, x, symbol, style),
                on_highlight = lambda x: self.highlight_entry(locations, x))


if __name__ == '__main__':

    assert build_import_statement('test', '/a/b/c/test.py') == "from a.b.c.test import test"
    assert build_import_statement('test', '/a/b/c/test.py', 'a') == "from b.c.test import test"
    assert build_import_statement('test', '/a/b/c/test.py', 'a/') == "from b.c.test import test"
    assert build_import_statement('test', '/a/b/c/test.py', '/a') == "from b.c.test import test"
    assert build_import_statement('test', '/a/b/c/test.py', '/a/') == "from b.c.test import test"
    assert build_import_statement('test', '/a/b/c/__init__.py') == "from a.b.c import test"
    assert build_import_statement('test', '/a/b/c.py') == "from a.b.c import test"
    assert build_import_statement('test', '/a/b/c/test.py', style=ImportStyle.ABSOLUTE) == "import a.b.c.test.test"
    assert build_import_statement('test', '/a/b/c/__init__.py', style=ImportStyle.ABSOLUTE) == "import a.b.c.test"
