# Module 'os2emxpath' -- common operations on OS/2 pathnames
"""Common pathname manipulations, OS/2 EMX version.

Instead of importing this module directly, import os and refer to this
module as os.path.
"""

import os
import stat
from genericpath import *
from ntpath import (expanduser, expandvars, isabs, islink, splitdrive,
                    splitext, split, walk)

__all__ = ["normcase","isabs","join","splitdrive","split","splitext",
           "basename","dirname","commonprefix","getsize","getmtime",
           "getatime","getctime", "islink","exists","lexists","isdir","isfile",
           "ismount","walk","expanduser","expandvars","normpath","abspath",
           "samefile","sameopenfile","samestat",
           "splitunc","curdir","pardir","sep","pathsep","defpath","altsep",
           "extsep","devnull","realpath","supports_unicode_filenames"]

# strings representing various path-related bits and pieces
curdir = '.'
pardir = '..'
extsep = '.'
sep = '/'
altsep = '\\'
pathsep = ';'
defpath = '.;' + (os.environ['UNIXROOT'] + '\\usr\\bin' if 'UNIXROOT' in os.environ else 'C:\\bin')
devnull = 'nul'

# Normalize the case of a pathname and map slashes to backslashes.
# Other normalizations (such as optimizing '../' away) are not done
# (this is done by normpath).

def normcase(s):
    """Normalize case of pathname.

    Makes all characters lowercase and all altseps into seps."""
    return s.replace(altsep, sep).lower()


# Join two (or more) paths.

def join(a, *p):
    """Join two or more pathname components, inserting sep as needed.

    Also replaces all altsep chars with sep in the returned string
    to make it consistent."""
    path = a
    for b in p:
        if isabs(b):
            path = b
        elif path == '' or path[-1:] in '/\\:':
            path = path + b
        else:
            path = path + '/' + b
    return path.replace(altsep, sep)


# Parse UNC paths
def splitunc(p):
    """Split a pathname into UNC mount point and relative path specifiers.

    Return a 2-tuple (unc, rest); either part may be empty.
    If unc is not empty, it has the form '//host/mount' (or similar
    using backslashes).  unc+rest is always the input path.
    Paths containing drive letters never have an UNC part.
    """
    if p[1:2] == ':':
        return '', p # Drive letter present
    firstTwo = p[0:2]
    if firstTwo == '/' * 2 or firstTwo == '\\' * 2:
        # is a UNC path:
        # vvvvvvvvvvvvvvvvvvvv equivalent to drive letter
        # \\machine\mountpoint\directories...
        #           directory ^^^^^^^^^^^^^^^
        normp = normcase(p)
        index = normp.find('/', 2)
        if index == -1:
            ##raise RuntimeError, 'illegal UNC path: "' + p + '"'
            return ("", p)
        index = normp.find('/', index + 1)
        if index == -1:
            index = len(p)
        return p[:index], p[index:]
    return '', p


# Return the tail (basename) part of a path.

def basename(p):
    """Returns the final component of a pathname"""
    return split(p)[1]


# Return the head (dirname) part of a path.

def dirname(p):
    """Returns the directory component of a pathname"""
    return split(p)[0]


# Is a path a directory?

# Is a path a mount point?  Either a root (with or without drive letter)
# or an UNC path with at most a / or \ after the mount point.

def ismount(path):
    """Test whether a path is a mount point (defined as root of drive)"""
    unc, rest = splitunc(path)
    if unc:
        return rest in ("", "/", "\\")
    p = splitdrive(path)[1]
    return len(p) == 1 and p[0] in '/\\'


# Normalize a path, e.g. A//B, A/./B and A/foo/../B all become A/B.

def normpath(path):
    """Normalize path, eliminating double slashes, etc."""
    path = path.replace('\\', '/')
    prefix, path = splitdrive(path)
    while path[:1] == '/':
        prefix = prefix + '/'
        path = path[1:]
    comps = path.split('/')
    i = 0
    while i < len(comps):
        if comps[i] == '.':
            del comps[i]
        elif comps[i] == '..' and i > 0 and comps[i-1] not in ('', '..'):
            del comps[i-1:i+1]
            i = i - 1
        elif comps[i] == '' and i > 0 and comps[i-1] != '':
            del comps[i]
        else:
            i = i + 1
    # If the path is now empty, substitute '.'
    if not prefix and not comps:
        comps.append('.')
    return prefix + '/'.join(comps)


# Return an absolute path.
def abspath(path):
    """Return the absolute version of a path"""
    if not isabs(path):
        path = join(os.getcwd(), path)
    return normpath(path)


# Return a canonical path (i.e. the absolute location of a file on the
# filesystem).

def realpath(filename):
    """Return the canonical path of the specified filename, eliminating any
symbolic links encountered in the path."""
    if isabs(filename):
        bits = ['/'] + filename.split('/')[1:]
    else:
        bits = [''] + filename.split('/')

    for i in range(2, len(bits)+1):
        component = join(*bits[0:i])
        # Resolve symbolic links.
        if islink(component):
            resolved = _resolve_link(component)
            if resolved is None:
                # Infinite loop -- return original component + rest of the path
                return abspath(join(*([component] + bits[i:])))
            else:
                newpath = join(*([resolved] + bits[i:]))
                return realpath(newpath)

    return abspath(filename)


def _resolve_link(path):
    """Internal helper function.  Takes a path and follows symlinks
    until we either arrive at something that isn't a symlink, or
    encounter a path we've seen before (meaning that there's a loop).
    """
    paths_seen = []
    while islink(path):
        if path in paths_seen:
            # Already seen this path, so we must have a symlink loop
            return None
        paths_seen.append(path)
        # Resolve where the link points to
        resolved = os.readlink(path)
        if not isabs(resolved):
            dir = dirname(path)
            path = normpath(join(dir, resolved))
        else:
            path = normpath(resolved)
    return path


# Is a path a symbolic link?
# This will always return false on systems where os.lstat doesn't exist.

def islink(path):
    """Test whether a path is a symbolic link"""
    try:
        st = os.lstat(path)
    except (os.error, AttributeError):
        return False
    return stat.S_ISLNK(st.st_mode)

# Being true for dangling symbolic links is also useful.

def lexists(path):
    """Test whether a path exists.  Returns True for broken symbolic links"""
    try:
        st = os.lstat(path)
    except os.error:
        return False
    return True


# Are two filenames really pointing to the same file?

def samefile(f1, f2):
    """Test whether two pathnames reference the same actual file"""
    s1 = os.stat(f1)
    s2 = os.stat(f2)
    return samestat(s1, s2)


# Are two open files really referencing the same file?
# (Not necessarily the same file descriptor!)

def sameopenfile(fp1, fp2):
    """Test whether two open file objects reference the same file"""
    s1 = os.fstat(fp1)
    s2 = os.fstat(fp2)
    return samestat(s1, s2)


# Are two stat buffers (obtained from stat, fstat or lstat)
# describing the same file?

def samestat(s1, s2):
    """Test whether two stat buffers reference the same file"""
    return s1.st_ino == s2.st_ino and \
           s1.st_dev == s2.st_dev


supports_unicode_filenames = False


def relpath(path, start=curdir):
    """Return a relative version of a path"""

    if not path:
        raise ValueError("no path specified")
    start_list = abspath(start).split(sep)
    path_list = abspath(path).split(sep)
    # Remove empty components after trailing slashes
    if (start_list[-1] == ''):
        start_list.pop()
    if (path_list[-1] == ''):
        path_list.pop()
    if start_list[0].lower() != path_list[0].lower():
        unc_path, rest = splitunc(path)
        unc_start, rest = splitunc(start)
        if bool(unc_path) ^ bool(unc_start):
            raise ValueError("Cannot mix UNC and non-UNC paths (%s and %s)"
                                                                % (path, start))
        else:
            raise ValueError("path is on drive %s, start on drive %s"
                                                % (path_list[0], start_list[0]))
    # Work out how much of the filepath is shared by start and path.
    for i in range(min(len(start_list), len(path_list))):
        if start_list[i].lower() != path_list[i].lower():
            break
    else:
        i += 1

    rel_list = [pardir] * (len(start_list)-i) + path_list[i:]
    if not rel_list:
        return curdir
    return join(*rel_list)
