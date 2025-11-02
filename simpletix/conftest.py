# conftest.py
import os
import sys
from unittest import mock

# make sure tests never try to talk to real Algolia
os.environ.setdefault("DJANGO_DISABLE_ALGOLIA", "1")

# in case something still imports these, mock them
sys.modules.setdefault("algoliasearch", mock.MagicMock())
sys.modules.setdefault("algoliasearch_django", mock.MagicMock())
