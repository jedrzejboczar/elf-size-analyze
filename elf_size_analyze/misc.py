"""
Miscellaneous helper functions
"""

# construct python regex named group
def g(name, regex):
    return r'(?P<{}>{})'.format(name, regex)


# print human readable size
# https://stackoverflow.com/questions/1094841/reusable-library-to-get-human-readable-version-of-file-size
def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            suffix_str = unit + suffix
            return "%3.1f %-3s" % (num, suffix_str)
        num /= 1024.0
    unit = 'Yi'
    suffix_str = unit + suffix
    return "%3.1f %-3s" % (num, suffix_str)