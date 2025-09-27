# This script demonstrates that the result of a find* method can
# generally be assigned to either Tag, NavigableString, Sequence[Tag],
# or Sequence[NavigableString], depending on usage.
from typing import Optional, Sequence
from bs4 import BeautifulSoup, Tag, NavigableString
soup = BeautifulSoup("<p>", 'html.parser')

tag:Optional[Tag]
string:Optional[NavigableString]
tags:Sequence[Tag]
strings:Sequence[NavigableString]

tag = soup.find()
tag = soup.find(id="a")
string = soup.find(string="b")

tags = soup()
tags = soup(id="a")
strings = soup(string="b")

tags = soup.find_all()
tags = soup.find_all(id="a")
strings = soup.find_all(string="b")

tag = soup.find_next()
tag = soup.find_next(id="a")
string = soup.find_next(string="b")

tags = soup.find_all_next()
tags = soup.find_all_next(id="a")
strings = soup.find_all_next(string="b")

tag = soup.find_next_sibling()
tag = soup.find_next_sibling(id="a")
string = soup.find_next_sibling(string="b")

tags = soup.find_next_siblings()
tags = soup.find_next_siblings(id="a")
strings = soup.find_next_siblings(string="b")

tag = soup.find_previous()
tag = soup.find_previous(id="a")
string = soup.find_previous(string="b")

tags = soup.find_all_previous()
tags = soup.find_all_previous(id="a")
strings = soup.find_all_previous(string="b")

tag = soup.find_previous_sibling()
tag = soup.find_previous_sibling(id="a")
string = soup.find_previous_sibling(string="bold")

tags = soup.find_previous_siblings()
tags = soup.find_previous_siblings(id="a")
strings = soup.find_previous_siblings(string="b")

tag = soup.find_parent()
tag = soup.find_parent(id="a")
tags = soup.find_parents()
tags = soup.find_parents(id="a")

# This code will work, but mypy and pyright will both flag it.
tags = soup.find_all("a", string="b")
