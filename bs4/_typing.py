# Custom type aliases used throughout Beautiful Soup to improve readability.

# Notes on improvements to the type system in newer versions of Python
# that can be used once Beautiful Soup drops support for older
# versions:
#
# * In 3.10, x|y is an accepted shorthand for Union[x,y].
# * In 3.10, TypeAlias gains capabilities that can be used to
#   improve the tree matching types (I don't remember what, exactly).
# * In 3.9 it's possible to specialize the re.Match type,
#   e.g. re.Match[str]. In 3.8 there's a typing.re namespace for this,
#   but it's removed in 3.12, so to support the widest possible set of
#   versions I'm not using it.

import re
from typing_extensions import (
    runtime_checkable,
    Protocol,
    TypeAlias,
)
from typing import (
    Any,
    Callable,
    Dict,
    IO,
    Iterable,
    Optional,
    Pattern,
    TYPE_CHECKING,
    Union,
)

if TYPE_CHECKING:
    from bs4.element import PageElement, Tag

# Protocol object that covers Python's built-in re.Pattern objects,
# and the similar Regex objects defined by the third-party regex
# package.
@runtime_checkable
class _RegularExpressionProtocol(Protocol):
    def search(self, string:str, pos:int=..., endpos:int=...) -> Optional[Any]:
        ...

    @property
    def pattern(self) -> str:
        ...

# Aliases for markup in various stages of processing.
#
# The rawest form of markup: either a string or an open filehandle.
_IncomingMarkup: TypeAlias = Union[str,bytes,IO[str],IO[bytes]]

# Markup that is in memory but has (potentially) yet to be converted
# to Unicode.
_RawMarkup: TypeAlias = Union[str,bytes]

# Aliases for character encodings
#
_Encoding:TypeAlias = str
_Encodings:TypeAlias = Iterable[_Encoding]

# Aliases for XML namespaces
_NamespacePrefix:TypeAlias = str
_NamespaceURL:TypeAlias = str
_NamespaceMapping:TypeAlias = Dict[_NamespacePrefix, _NamespaceURL]
_InvertedNamespaceMapping:TypeAlias = Dict[_NamespaceURL, _NamespacePrefix]

# Aliases for the attribute values associated with HTML/XML tags.
#
# These are the relatively unprocessed values Beautiful Soup expects
# to come from a `TreeBuilder`.
_RawAttributeValue: TypeAlias = str
_RawAttributeValues: TypeAlias = Dict[str, _RawAttributeValue]

# These are attribute values in their final form, as stored in the
# `Tag` class, after they have been processed and (in some cases)
# split into lists of strings.
_AttributeValue: TypeAlias = Union[str, Iterable[str]]
_AttributeValues: TypeAlias = Dict[str, _AttributeValue]

# The methods that deal with turning _RawAttributeValues into
# _AttributeValues may be called several times, even after the values
# are already processed (e.g. when cloning a tag), so they need to
# be able to acommodate both possibilities.
_RawOrProcessedAttributeValues:TypeAlias = Union[_RawAttributeValues, _AttributeValues]

# A number of tree manipulation methods can take either a PageElement or a
# normal Python string (which will be converted to a NavigableString).
_InsertableElement:TypeAlias = Union['PageElement',str]

# Aliases to represent the many possibilities for matching bits of a
# parse tree.
#
# This is very complicated because we're applying a formal type system
# to some very DWIM code. The types we end up with will be the types
# of the arguments to the SoupStrainer constructor and (more
# familiarly to Beautiful Soup users) the find* methods.

# A function that takes a PageElement and returns a yes-or-no answer.
_PageElementMatchFunction:TypeAlias = Callable[['PageElement'], bool]

# A function that takes the raw parsed ingredients of a markup tag
# and returns a yes-or-no answer.
_AllowTagCreationFunction:TypeAlias = Callable[[Optional[str], str, Optional[_RawAttributeValues]], bool]

# A function that takes the raw parsed ingredients of a markup string node
# and returns a yes-or-no answer.
_AllowStringCreationFunction:TypeAlias = Callable[[Optional[str]], bool]

# A function that takes a Tag and returns a yes-or-no answer.
# A TagNameMatchRule expects this kind of function, if you're
# going to pass it a function.
_TagMatchFunction:TypeAlias = Callable[['Tag'], bool]

# A function that takes a single string and returns a yes-or-no
# answer. An AttributeValueMatchRule expects this kind of function, if
# you're going to pass it a function. So does a StringMatchRule
_StringMatchFunction:TypeAlias = Callable[[str], bool]

# Either a tag name, an attribute value or a string can be matched
# against a string, bytestring, regular expression, or a boolean.
_BaseStrainable:TypeAlias = Union[str, bytes, Pattern[str], bool]

# A tag can also be matched using a function that takes the Tag
# as its sole argument.
_BaseStrainableElement:TypeAlias = Union[_BaseStrainable, _TagMatchFunction]

# A tag's attribute value can be matched using a function that takes
# the value as its sole argument.
_BaseStrainableAttribute:TypeAlias = Union[_BaseStrainable, _StringMatchFunction]

# Finally, a tag name, attribute or string can be matched using either
# a single criterion or a list of criteria.
_StrainableElement:TypeAlias = Union[
    _BaseStrainableElement, Iterable[_BaseStrainableElement]
]
_StrainableAttribute:TypeAlias = Union[
    _BaseStrainableAttribute, Iterable[_BaseStrainableAttribute]
]

_StrainableAttributes:TypeAlias = Dict[str, _StrainableAttribute]
_StrainableString:TypeAlias = _StrainableAttribute
