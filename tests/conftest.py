import sys
from unittest.mock import MagicMock

# this runs before all other tests start importing things, so the server
# doesn't complain about not having this file
sys.modules["code._login"] = MagicMock()
