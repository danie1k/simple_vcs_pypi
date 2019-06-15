import collections
from http import HTTPStatus
from urllib import parse

from cachelib import FileSystemCache
from github3 import (
    GitHub as GitHubApi,
    exceptions as gh_exc,
    repos,
)
from github3.repos import release
import requests
from werkzeug import (
    exceptions,
    routing,
    wrappers,
)

from gh_pypi import (
    github,
    templates,
)
from gh_pypi.stream_response import ResponseStream

__all__ = ('WsgiApplication', )

ASSET_FILENAME = 'pypi.tar.gz'
CACHE_KEY = 'repositories'


# noinspection PyMethodMayBeStatic,PyProtectedMember,PyUnusedLocal,SpellCheckingInspection
class WsgiApplication(github.GitHub):  # pylint:disable=too-many-instance-attributes
    _URLS = routing.Map((
        routing.Rule('/', endpoint='index'),
        routing.Rule('/<repository_name>/', endpoint='repository'),
        routing.Rule('/<repository_name>/release/<release_name>.tar.gz', endpoint='download'),
    ))

    _cache = None  # type: FileSystemCache
    _users_and_organizations = None  # type: (github.Organization | github.User, ...)
    _index_template = None  # type: str
    _repository_template = None  # type: str
    _auth = None  # type: dict[str]
    _request_domain = None  # type: str
    _request_urls = None  # type: routing.MapAdapter

    @property
    def repositories(self):
        """
        :rtype: dict[str, repos.ShortRepository]
        """
        value = self._cache.get(CACHE_KEY)

        if value is None:
            data = self.get_installable_repositories(*self._users_and_organizations)
            value = {key: repo._json_data for key, repo in data.items()}  # pylint:disable=protected-access
            self._cache.set(CACHE_KEY, value)
            return data

        return {key: repos.ShortRepository(json, self.github_api.session) for key, json in value.items()}

    # noinspection PyTypeChecker
    def __init__(
            self,
            *users_and_organizations,
            cache_dir,  # Should be an absolute path!
            index_template=None,
            repository_template=None,
    ) -> None:
        """
        :type users_and_organizations: (github.Organization | github.User, ...)
        :type index_template: str
        :type repository_template: str
        :rtype: None
        """
        self._cache = FileSystemCache(cache_dir=cache_dir, default_timeout=900)
        self._users_and_organizations = users_and_organizations
        self._index_template = index_template or templates.INDEX
        self._repository_template = repository_template or templates.REPOSITORY
        self._auth = None
        self._request_domain = None
        self._request_urls = None
        self.current_user = None
        self.github_api = None

    def __call__(self, environ, start_response):
        """
        :type environ: dict
        :type start_response: werkzeug.serving.WSGIRequestHandler.start_response
        :rtype: werkzeug.wsgi.ClosingIterator
        """
        request = wrappers.Request(environ)

        if b'purge_cache' in request.query_string:
            self._cache.delete(CACHE_KEY)

        try:
            self._get_authorization(request)
            self._authorize_github()
            self._request_domain = self._get_request_domain(request)

            self._request_urls = self._URLS.bind_to_environ(request.environ)
            endpoint, values = self._request_urls.match()

            func_name = 'dispatch_{}'.format(endpoint)
            response = (
                getattr(self, func_name)(request, **values) if hasattr(self, func_name)
                else exceptions.NotFound()
            )
        except exceptions.HTTPException as ex:
            response = ex

        return response(environ, start_response)

    def _get_authorization(self, request):
        """
        :type request: werkzeug.wrappers.request.Request
        :rtype: dict[str]
        :raises werkzeug.exceptions.Unauthorized: If authorization information not available in `request`
        """
        auth = request.authorization or {}
        username = auth.get('username', '').strip()
        password = auth.get('password', '').strip()
        if not username:
            raise exceptions.Unauthorized(www_authenticate='Basic realm="Simple index"')

        self._auth = {'username': username, 'password': password} if username and password else {'token': username}

    def _authorize_github(self):
        """
        :rtype: None
        :raises werkzeug.exceptions.Forbidden: If cannot login to GitHub using `auth` credentials
        """
        self.github_api = GitHubApi(**self._auth)
        try:
            self.current_user = self.github_api.me()
        except gh_exc.AuthenticationFailed:
            raise exceptions.Forbidden()
        if self.current_user is None:
            raise exceptions.Forbidden()

    def _get_request_domain(self, request):
        """
        :type request: werkzeug.wrappers.request.Request
        :rtype: str
        """
        base_url = parse.urlsplit(request.base_url)  # type: parse.SplitResult
        netloc = (
            '{scheme}://{token}@{domain}' if 'token' in self._auth
            else '{scheme}://{username}:{password}@{domain}'
        )

        format_dict = {'domain': base_url.netloc.split('@')[-1].rstrip('/')}
        format_dict.update(self._auth)
        format_dict.update(base_url._asdict())

        return netloc.format(**format_dict)

    # Endpoints

    def dispatch_download(self, request, repository_name, release_name):  # pylint:disable=unused-argument
        repo_releases = self._get_releases(repository_name)
        if not repo_releases:
            raise exceptions.NotFound()

        wanted_release = repo_releases[release_name]  # type: release.Release
        asset_url = self._find_release_download_link(wanted_release)  # type: str

        with requests.get(asset_url, headers={'Accept': 'application/octet-stream'}, stream=True) as tarball:
            if tarball.status_code != HTTPStatus.OK:
                raise exceptions.NotFound()

            stream = ResponseStream(tarball.iter_content(1024))
            return wrappers.Response(stream.read(), direct_passthrough=True, mimetype='application/x-compressed')

    def dispatch_index(self, request):  # pylint:disable=unused-argument
        """
        :type request: werkzeug.wrappers.request.Request
        :rtype: werkzeug.wrappers.response.Response
        """
        return wrappers.Response(
            self._index_template % {
                'links': '\n'.join('<a href="%(domain)s%(endpoint)s">%(name)s</a>' % {
                    'domain': self._request_domain,
                    'endpoint': self._request_urls.build('repository', {'repository_name': repo_name}),
                    'name': repo.full_name,
                } for repo_name, repo in self.repositories.items()),
            },
            mimetype='text/html',
        )

    def dispatch_repository(self, request, repository_name):  # pylint:disable=unused-argument
        """
        :type request: werkzeug.wrappers.request.Request
        :type repository_name: str
        :rtype: werkzeug.wrappers.response.Response
        :raises werkzeug.exceptions.NotFound: If `repository_name` not found on GitHub
        """
        releases = self._get_repo_releases_links(repository_name)
        return wrappers.Response(
            self._repository_template % {
                'repository_name': repository_name,
                'links': '\n'.join('<a href="%(url)s">%(tag_name)s</a>' % item for item in releases),
            },
            mimetype='text/html',
        )

    # Helpers

    def _get_repo_releases_links(self, repository_name):
        """
        :type repository_name: str
        :rtype: (dict[str, str], ...) | None
        """
        repo_releases = self._get_releases(repository_name)
        if not repo_releases:
            return None

        return tuple({
            'url': '%(domain)s%(endpoint)s' % {
                'domain': self._request_domain,
                'endpoint': self._request_urls.build('download', {
                    'repository_name': repository_name,
                    'release_name': tag_name
                }),
            },
            'tag_name': tag_name
        } for tag_name in repo_releases.keys())

    def _get_releases(self, repository_name):
        """
        :type repository_name: str
        :rtype: dict[str, release.Release] | None
        """
        repositories_with_aliases = {}
        for key, value in self.repositories.items():
            repositories_with_aliases[key] = value
            repositories_with_aliases[key.replace('_', '-')] = value

        try:
            repository = repositories_with_aliases[repository_name]  # type: repos.ShortRepository
        except KeyError:
            raise exceptions.NotFound()

        repo_releases = collections.OrderedDict(
            (item.tag_name, item)
            for item in sorted(repository.releases(), key=lambda item: item.created_at)
        )
        return repo_releases or None

    def _find_release_download_link(self, release_instance):
        """
        :type: release.Release
        :rtype: str
        :raises werkzeug.exceptions.NotFound:
        """
        asset_url = None
        for asset in release_instance.assets():  # type: release_instance.Asset
            if asset.name == ASSET_FILENAME:
                asset_url = '{download_url}?access_token={access_token}'.format(
                    download_url=asset.download_url,
                    access_token=self._auth.get('token', self._auth.get('password')),
                )
                break

        if not asset_url:
            raise exceptions.NotFound(
                'Asset "{}" not found in release "{}"'.format(ASSET_FILENAME, release_instance.name)
            )
        return asset_url
