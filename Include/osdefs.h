// Operating system dependencies.
//
// Define constants:
//
// - ALTSEP
// - DELIM
// - MAXPATHLEN
// - SEP

#ifndef Py_OSDEFS_H
#define Py_OSDEFS_H
#ifdef __cplusplus
extern "C" {
#endif

#ifdef MS_WINDOWS
#  define SEP L'\\'
#  define ALTSEP L'/'
#  define MAXPATHLEN 256
#  define DELIM L';'
#endif

#ifdef __OS2__
#ifndef MAXPATHLEN
#define MAXPATHLEN 260
#endif
#define SEP L'/'
#define ALTSEP L'\\'
#define DRVSEP L':'
#define DELIM L';'
#endif

#ifdef __VXWORKS__
#  define DELIM L';'
#endif

/* Filename separator */
#ifndef SEP
#  define SEP L'/'
#endif

/* Test if `ch' is a filename separator (bird) */
#ifdef ALTSEP
#define IS_SEP(ch) ((ch) == SEP || (ch) == ALTSEP)
#else
#define IS_SEP(ch) ((ch) == SEP)
#endif

/* Test if `path' has a drive letter or not. (bird) */
#ifdef DRVSEP
#define HAS_DRV(path) (*(path) && (path)[1] == DRVSEP)
#else
#define HAS_DRV(path) 0
#endif

/* Test if `path' is absolute or not. (bird) */
#ifdef DRVSEP
#define IS_ABSPATH(path) (IS_SEP((path)[0]) || HAS_DRV(path))
#else
#define IS_ABSPATH(path) (IS_SEP((path)[0]))
#endif

/* Test if `path' contains any of the path separators including drive letter. (bird) */
#ifdef ALTSEP
#define HAS_ANYSEP(path) ( wcschr((path), SEP) || wcschr((path), ALTSEP) || HAS_DRV(path) )
#else
#define HAS_ANYSEP(path) ( wcschr((path), SEP) || HAS_DRV(path) )
#endif

/* Max pathname length */
#ifdef __hpux
#  include <sys/param.h>
#  include <limits.h>
#  ifndef PATH_MAX
#    define PATH_MAX MAXPATHLEN
#  endif
#endif

#ifndef MAXPATHLEN
#  if defined(PATH_MAX) && PATH_MAX > 1024
#    define MAXPATHLEN PATH_MAX
#  else
#    define MAXPATHLEN 1024
#  endif
#endif

/* Search path entry delimiter */
#ifndef DELIM
#  define DELIM L':'
#endif

#ifdef __cplusplus
}
#endif
#endif   // !Py_OSDEFS_H
