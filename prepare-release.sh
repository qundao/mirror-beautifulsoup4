# A script to automatically create and test source and wheel
# distributions of Beautiful Soup.

# Recommend you run these steps one at a time rather than just running
# the script.

# If you screwed up on the test server and have to create a "a" or "b"
# release the second time, add the '--pre' argument to pip install to
# find the 'prerelease'.

# At some point I'll become confident enough with hatch and tox
# that it won't be necessary to do so many install and test steps.

# First, change the version number in
#  CHANGELOG
#  bs4/__init__.py
#  doc/index.rst

pyenv activate bs4-test
hatch clean
tox run-parallel

# Build sdist and wheel.
hatch build

# Test the sdist locally.
pyenv virtualenv-delete py3-install-test-virtualenv
pyenv virtualenv 3.13.1 py3-install-test-virtualenv
pyenv activate py3-install-test-virtualenv
pip install dist/beautifulsoup4-*.tar.gz pytest lxml html5lib soupsieve
python -m pytest ~/.pyenv/versions/3.13.*/envs/py3-install-test-virtualenv/lib/python3.13/site-packages/bs4/tests
echo "EXPECT HTML ON LINE BELOW"
(cd .. && python --version && python -c "from bs4 import _s, __version__; print(__version__, _s('<a>foo', 'lxml'))")
# That should print something like:
# Python 3.13.1
# [new version number] <a>foo</a>


# Test the wheel locally.
pip uninstall beautifulsoup4
pip install dist/beautifulsoup4-*.whl
echo "EXPECT HTML ON LINE BELOW"
(cd .. && python --version && python -c "from bs4 import _s, __version__; print(__version__, _s('<a>foo', 'lxml'))")

pyenv deactivate
pyenv virtualenv-delete py3-install-test-virtualenv

# Upload to test pypi
pyenv activate bs4-test
hatch publish -r test

# Test install from test pypi.
pyenv virtualenv 3.13.1 py3-install-test-virtualenv
pyenv activate py3-install-test-virtualenv
pip install pytest lxml html5lib soupsieve typing-extensions hatchling

# First, install from source and run the tests.
pip install -i https://test.pypi.org/simple/ beautifulsoup4 --extra-index-url=https://pypi.python.org/pypi --no-binary beautifulsoup4
python -m pytest ~/.pyenv/versions/py3-install-test-virtualenv/lib/python3.13/site-packages/bs4/
echo "EXPECT HTML ON LINE BELOW"
(cd .. && which python && python -c "from bs4 import _s, __version__; print(__version__, _s('<a>foo', 'lxml'))")
# That should print something like:
# /home/leonardr/.pyenv/shims/python
# [new version number] <a>foo</a>

# Next, install the wheel and just test functionality.
pip uninstall beautifulsoup4
pip install -i https://test.pypi.org/simple/ beautifulsoup4 --extra-index-url=https://pypi.python.org/pypi --no-binary beautifulsoup4
echo "EXPECT HTML ON LINE BELOW"
(cd .. && which python && python -c "from bs4 import _s, __version__; print(__version__, _s('<a>foo', 'lxml'))")
# That should print something like:
# /home/.../py3-install-test-virtualenv/bin/python
# [new version number] <a>foo</a>

pyenv virtualenv-delete py3-install-test-virtualenv

# Upload to production pypi
pyenv activate bs4-test
hatch publish

# Test install from production pypi

# First, from the source distibution
pyenv virtualenv-delete py3-install-test-virtualenv
pyenv virtualenv py3-install-test-virtualenv
pyenv activate py3-install-test-virtualenv

pip install pytest lxml html5lib beautifulsoup4 --no-binary beautifulsoup4
python -m pytest ~/.pyenv/versions/py3-install-test-virtualenv/lib/python3.*/site-packages/bs4/
echo "EXPECT HTML ON LINE BELOW"
(cd .. && which python && python -c "from bs4 import _s, __version__; print(__version__, _s('<a>foo', 'html.parser'))")
# That should print something like:
# /home/.../py3-install-test-virtualenv/bin/python
# [new version number] <a>foo</a>

# Next, from the wheel
pip uninstall beautifulsoup4
pip install beautifulsoup4
echo "EXPECT HTML ON LINE BELOW"
(cd .. && which python && python -c "from bs4 import _s, __version__; print(__version__, _s('<a>foo', 'html.parser'))")
# That should print something like:
# /home/.../py3-install-test-virtualenv/bin/python
# [new version number] <a>foo</a>

# Cleanup
pyenv virtualenv-delete py3-install-test-virtualenv
