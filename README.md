PythonAutoImport
================

An Python auto-import plugin for Sublime Text 3 (ST2 not supported)

## Overview
This plugin adds some helpers to allow you to automatically import Python objects under your cursor

## Installation
(You may need to restart Sublime Text 3 for the plugin to load)

### Package Control
Coming soon
<!---
Installation through [package control](http://wbond.net/sublime_packages/package_control) is recommended. It will handle updating your packages as they become available. To install, do the following.

* In the Command Palette, enter `Package Control: Install Package`
* Search for `PythonAutoImport`
* In the Command Palette, enter `Package Control: Enable Package` -> select PythonAutoImport
-->

### Manual
Clone or copy this repository into the packages directory. By default, they are located at:

* OS X: `~/Library/Application Support/Sublime Text 3/Packages/`
* Windows: `%APPDATA%/Roaming/Sublime Text 3/Packages/`
* Linux: `~/.config/sublime-text-3/Packages/`

`git clone git@github.com:jasonmyers/PythonAutoImport.git`

## Usage
Position your cursor over the object you wish to import, and then activate PythonAutoImport either through the command palette or a keybinding

**Root path:**
Set where you wish your imports to be relative from in the `root_path` setting

For example, if import is created as

    from x.y.z import a

and your normal import path is

    from z import a

set `root_path` to be `/x/y/`

## Keymaps

### Windows
`ctrl+alt+i`:  Import the object under the cursor (using `from x import y`)

`ctrl+alt+shift_i`:  Import the object under the cursor (using 'import x.y`)

### OS X and Linux
The super keys for Linux and OS X are the Windows and command key respectively.

`super+alt+i`: Import the object under the cursor (using `from x import y`)

`shift+super+alt+i`: Import the object under the cursor (using 'import x.y`)

## Settings
`root_path`:

Set this to the root path of your project, so that imports are created relative to it

`scroll_to_import`:

Whether to scroll to the new import after it is added

### Contributors
* [jmyers](https://github.com/jmyers)
