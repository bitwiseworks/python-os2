#ifndef Py_OSDEFS_H
#define Py_OSDEFS_H
#ifdef __cplusplus
extern "C" {
#endif


/* Operating system dependencies */

/* Mod by chrish: QNX has WATCOM, but isn't DOS */
#if !defined(__QNX__)
#if defined(MS_WINDOWS) || defined(__BORLANDC__) || defined(__WATCOMC__) || defined(__DJGPP__) || defined(PYOS_OS2)
#if defined(PYOS_OS2) && defined(PYCC_GCC)
#define MAXPATHLEN 260
#define SEP '/'
#define ALTSEP '\\'
#else
#define SEP '\\'
#define ALTSEP '/'
#define MAXPATHLEN 256
#endif
#define DRVSEP ':' /* (bird) */
#define DELIM ';'
#endif
#endif

#ifdef RISCOS
#define SEP '.'
#define MAXPATHLEN 256
#define DELIM ','
#endif


/* Filename separator */
#ifndef SEP
#define SEP '/'
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
#define HAS_ANYSEP(path) ( strchr((path), SEP) || strchr((path), ALTSEP) || HAS_DRV(path) )
#else
#define HAS_ANYSEP(path) ( strchr((path), SEP) || HAS_DRV(path) )
#endif

/* Max pathname length */
#ifdef __hpux
#include <sys/param.h>
#include <limits.h>
#ifndef PATH_MAX
#define PATH_MAX MAXPATHLEN
#endif
#endif

#ifndef MAXPATHLEN
#if defined(PATH_MAX) && PATH_MAX > 1024
#define MAXPATHLEN PATH_MAX
#else
#define MAXPATHLEN 1024
#endif
#endif

/* Search path entry delimiter */
#ifndef DELIM
#define DELIM ':'
#endif

#ifdef __cplusplus
}
#endif
#endif /* !Py_OSDEFS_H */
