"""Helper functions for deprecation."""
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
        return with_warning
    return deprecate
