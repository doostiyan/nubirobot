from ..main import IS_PROD, IS_TESTNET
from .common import *

if IS_PROD:
    from .prod import *
elif IS_TESTNET:
    from .testnet import *
else:
    from .debug import *
