import os
from gh_pypi import WsgiApplication

application = WsgiApplication(
    cache_dir=os.path.join(os.path.dirname(__file__), 'tmp'),
)
