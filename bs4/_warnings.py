"""Define some custom warnings."""


class GuessedAtParserWarning(UserWarning):
    """The warning issued when BeautifulSoup has to guess what parser to
    use -- probably because no parser was specified in the constructor.
    """


class UnusualUsageWarning(UserWarning):
    """A superclass for warnings issued when Beautiful Soup sees
    something that is typically the result of a mistake in the calling
    code, but might be intentional on the part of the user. If it is
    in fact intentional, you can filter the individual warning class
    to get rid of the warning. If you don't like Beautiful Soup
    second-guessing what you are doing, you can filter the
    UnusualUsageWarningclass itself and get rid of these entirely.
    """


class MarkupResemblesLocatorWarning(UnusualUsageWarning):
    """The warning issued when BeautifulSoup is given 'markup' that
    actually looks like a resource locator -- a URL or a path to a file
    on disk.
    """


class AttributeResemblesVariableWarning(UnusualUsageWarning, SyntaxWarning):
    """The warning issued when Beautiful Soup suspects a provided
    attribute name may actually be the misspelled name of a Beautiful
    Soup variable. Generally speaking, this is only used in cases like
    "_class" where it's very unlikely the user would be referencing an
    XML attribute with that name.
    """


class XMLParsedAsHTMLWarning(UnusualUsageWarning):
    """The warning issued when an HTML parser is used to parse
    XML that is not (as far as we can tell) XHTML.
    """
    MESSAGE: str = """It looks like you're parsing an XML document using an HTML parser. If this really is an HTML document (maybe it's XHTML?), you can ignore or filter this warning. If it's XML, you should know that using an XML parser will be more reliable. To parse this document as XML, make sure you have the lxml package installed, and pass the keyword argument `features="xml"` into the BeautifulSoup constructor."""  #: :meta private:
