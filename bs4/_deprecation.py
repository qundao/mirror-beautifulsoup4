"""Helper functions for deprecation.

This interface is itself unstable and may change without warning. Do
not use these functions yourself, even as a joke. The underscores are
there for a reson.

In particular, most of this will go away once Beautiful Soup drops
support for Python 3.11, since Python 3.12 defines a
`@typing.deprecated() decorator. <https://peps.python.org/pep-0702/>`_
"""

import functools
import warnings

def _alias(attr):
    """Alias one attribute name to another for backward compatibility

    :meta private:
    """
    @property
    def alias(self):
        return getattr(self, attr)

    @alias.setter
    def alias(self, value):
        return setattr(self, attr, value)
    return alias


def _deprecated_alias(old_name, new_name, version):
    """Alias one attribute name to another for backward compatibility

    :meta private:
    """
    @property
    def alias(self):
        ":meta private:"
        warnings.warn(f"Access to deprecated property {old_name}. (Replaced by {new_name}) -- Deprecated since version {version}.", DeprecationWarning, stacklevel=2)
        return getattr(self, new_name)

    @alias.setter
    def alias(self, value):
        ":meta private:"
        warnings.warn(f"Write to deprecated property {old_name}. (Replaced by {new_name}) -- Deprecated since version {version}.", DeprecationWarning, stacklevel=2)
        return setattr(self, new_name, value)
    return alias

def _deprecated_function_alias(old_name, new_name, version):
    def alias(self, *args, **kwargs):
        ":meta private:"
        warnings.warn(f"Call to deprecated method {old_name}. (Replaced by {new_name}) -- Deprecated since version {version}.", DeprecationWarning, stacklevel=2)
        return getattr(self, new_name)(*args, **kwargs)
    return alias

def _deprecated(replaced_by, version):
    def deprecate(func):
        @functools.wraps(func)
        def with_warning(*args, **kwargs):
            ":meta private:"
            warnings.warn(
                f"Call to deprecated method {func.__name__}. (Replaced by {replaced_by}) -- Deprecated since version {version}.",
                DeprecationWarning,
                stacklevel=2
            )
            return func(*args, **kwargs)
        return with_warning
    return deprecate
