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
#define OS2_SEP(ch) ((ch) == SEP || (ch) == ALTSEP)
#define OS2_DRV(path) (*(path) && (path)[1] == DRVSEP)
#define OS2_ABSPATH(path) (OS2_SEP((path)[0]) || OS2_DRV(path))
#define OS2_ANYSEP(path) ( wcschr((path), SEP) || wcschr((path), ALTSEP) || OS2_DRV(path) )
#endif

#ifdef __VXWORKS__
#  define DELIM L';'
#endif

/* Filename separator */
#ifndef SEP
#  define SEP L'/'
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
