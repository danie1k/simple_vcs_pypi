import os

from simple_vcs_pypi import WsgiApplication

application = WsgiApplication(
    cache_dir=os.path.join(os.path.dirname(__file__), 'tmp'),
)
