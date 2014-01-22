#!/usr/bin/env python3

# Parses .desktop files in DIRS and displays them in a dmenu instance.
# Based on dmenu selection it then execs the corresponding .desktop file, or whatever the
# command line the user typed in.
# Caches the .desktop files data in CACHE_FILE to speed startup, cache is invalidated
# by file system timestamps.
#
# Allows for user adjusted .desktop files to overwrite system ones (e.g. to fix Skypes pulse audio woes)
#
# @see .desktop spec is here: http://standards.freedesktop.org/desktop-entry-spec/desktop-entry-spec-latest.html#value-types

import os, subprocess, re, pickle
from glob import glob
from itertools import chain
from configparser import RawConfigParser

TERMINAL="/usr/bin/urxvt" #TODO: Use a freedesktop.org standard to work this out?
HOME_DIR=os.environ["HOME"]
CACHE_FILE=HOME_DIR + "/.cache/dmenu_applications"
# Earlier directories take priority over later ones for name conflicts. Use this
# to have customised launchers for applications.
DIRS=[HOME_DIR + "/bin/applications/", "/usr/share/applications/"]

def get_results_list():
   if is_valid_cache(CACHE_FILE):
      return pickle.load(open(CACHE_FILE, 'rb'))
   else:
      results = parse_desktop_files()
      pickle.dump(results, open(CACHE_FILE, 'wb'))
      return results

def is_valid_cache(CACHE_FILE):
   if os.path.isfile(CACHE_FILE):
      dirs_mtime=max((os.path.getmtime(dirname) for dirname in DIRS))
      cache_mtime=os.path.getmtime(CACHE_FILE)
      return cache_mtime >= dirs_mtime
   else:
      return False

def parse_desktop_files():
   desktop_files = chain(*[glob(directory + "*desktop") for directory in DIRS])
   entries = map(parse_file, desktop_files)
   candidates = filter(entry_visible, entries)

   # List of (name, app_data) tuples, use this instead of a dict so we
   # can have ordering. The number of entries should be small enough
   # for an O(n) lookup.
   results_list = []
   existing_names = {}
   for candidate in candidates:
      # The filename is used for the dmenu selection, as the "Name" key
      # is too verbose, and Exec may contain confounding factors like
      # execing via env
      filename = candidate["filename"].split("/")[-1][0:-8]
      name = bytes(filename.lower() + "\n", "ascii")
      if name in existing_names:
         continue
      else:
         existing_names[name] = True

      if "Path" in candidate:
         path = candidate["Path"]
      else:
         path = HOME_DIR

      results_list.append((name, {
         "command": candidate["Exec"],
         "terminal": "Terminal" in candidate and candidate["Terminal"] == "true",
         "path": path
      }))

   return sorted(results_list, key=lambda r: r[0])

def parse_file(filename):
   parser = RawConfigParser()
   parser.read(filename)
   entry = parser["Desktop Entry"]
   entry["filename"] = filename
   return entry

def entry_visible(entry):
   is_application = entry["Type"] == "Application"
   can_display = "NoDisplay" not in entry or entry["NoDisplay"] == "false"
   not_hidden = "Hidden" not in entry or entry["Hidden"] == "false"
   return is_application and can_display and not_hidden

def lookup(results_list, name):
   for (result_name, app_data) in results_list:
      if result_name == name:
         return app_data

   return None

results_list = get_results_list()

dmenu = subprocess.Popen(["dmenu"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
for (name,_) in results_list:
   dmenu.stdin.write(name)
dmenu.stdin.close()
dmenu.wait()
selection = dmenu.stdout.read()
dmenu.stdout.close()

if selection == b'':
   exit(0)
else:
   application = lookup(results_list, selection)
   if application == None:
      application = {
         "command": selection.decode("utf-8").strip(),
         "terminal": True,
         "path": HOME_DIR
      }

os.chdir(application["path"])
# Strip out all the special Exec % codes
command = re.sub("%[a-zA-Z] ?", "", application["command"])
if application["terminal"]:
   os.execv(TERMINAL, [TERMINAL, "-e", command])
else:
   os.execv("/bin/sh", ["/bin/sh", "-c", command])
