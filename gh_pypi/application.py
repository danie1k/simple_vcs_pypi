from urllib import parse

from cachelib import FileSystemCache
from github3 import (
    exceptions as gh_exc,
    login,
    repos,
)
from github3.repos import release
from werkzeug import (
    exceptions,
    routing,
    wrappers,
)

from . import (
    github,
    templates,
)

__all__ = ('WsgiApplication', )


# noinspection PyMethodMayBeStatic,PyProtectedMember,PyUnusedLocal,SpellCheckingInspection
class WsgiApplication(github.GitHub):
    _urls = routing.Map((
        routing.Rule('/', endpoint='index'),
        routing.Rule('/<repository_name>/', endpoint='repository'),
    ))

    _cache = None  # type: FileSystemCache
    _users_and_organizations = None  # type: (github.Organization | github.User, ...)
    _index_template = None  # type: str
    _repository_template = None  # type: str
    _request_domain = None  # type: str

    @property
    def repositories(self):
        """
        :rtype: dict[repos.ShortRepository]
        """
        value = self._cache.get('repositories')

        if value is None:
            data = self.get_installable_repositories(*self._users_and_organizations)
            value = {key: repo._json_data for key, repo in data.items()}  # pylint:disable=protected-access
            self._cache.set('repositories', value)
            return data

        return {key: repos.ShortRepository(json, self.github_api.session) for key, json in value.items()}

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
        # noinspection PyTypeChecker
        self._request_domain = None

    def __call__(self, environ, start_response):
        """
        :type environ: dict
        :type start_response: werkzeug.serving.WSGIRequestHandler.start_response
        :rtype: werkzeug.wsgi.ClosingIterator
        """
        request = wrappers.Request(environ)
        try:
            auth = self._get_authorization(request)
            self._authorize_github(**auth)
            self._request_domain = self._get_request_domain(request, **auth)

            adapter = self._urls.bind_to_environ(request.environ)
            endpoint, values = adapter.match()

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

        return {'username': username, 'password': password} if username and password else {'token': username}

    def _authorize_github(self, **auth):
        """
        :type auth: str
        :rtype: None
        :raises werkzeug.exceptions.Forbidden: If cannot login to GitHub using `auth` credentials
        """
        self.github_api = login(**auth)
        try:
            if self.github_api.me() is None:
                raise exceptions.Forbidden()
        except gh_exc.AuthenticationFailed:
            raise exceptions.Forbidden()

    def _get_request_domain(self, request, **auth):
        """
        :type request: werkzeug.wrappers.request.Request
        :type auth: str
        :rtype: str
        """
        base_url = parse.urlsplit(request.base_url)  # type: parse.SplitResult
        netloc = '{scheme}://{token}@{domain}/' if 'token' in auth else '{scheme}://{username}:{password}@{domain}/'
        return netloc.format(domain=base_url.netloc.split('@')[-1].rstrip('/'), **auth, **base_url._asdict())

    # Endpoints

    def dispatch_index(self, request):  # pylint:disable=unused-argument
        """
        :type request: werkzeug.wrappers.request.Request
        :rtype: werkzeug.wrappers.response.Response
        """
        return wrappers.Response(
            self._index_template % {
                'links': '\n'.join('<a href="%(domain)s%(name)s/">%(name)s</a>' % {
                    'domain': self._request_domain,
                    'name': repo,
                } for repo in self.repositories.keys()),
            },
            mimetype='text/html',
        )

    def dispatch_repository(self, request, repository_name):  # pylint:disable=unused-argument
        """
        :type request: werkzeug.wrappers.request.Request
        :param repository_name: str
        :rtype: werkzeug.wrappers.response.Response
        :raises werkzeug.exceptions.NotFound: If `repository_name` not found on GitHub
        """
        try:
            repository = self.repositories[repository_name]  # type: repos.ShortRepository
        except KeyError:
            raise exceptions.NotFound()

        releases = self._get_repo_releases(repository)
        if not releases:
            return wrappers.Response('No releases available for this repository', mimetype='text/html')

        return wrappers.Response(
            self._repository_template % {
                'repository_name': repository.name,
                'links': '\n'.join('<a href="%(url)s">%(name)s</a>' % item for item in releases),
            },
            mimetype='text/html',
        )

    def _get_repo_releases(self, repository):
        """
        :type repository: type: github3.repos.repo.repos.ShortRepository
        :rtype: (dict) | None
        """
        repo_releases = sorted(repository.releases(), key=lambda item: item.created_at)  # type: [release.Release]
        if not repo_releases:
            return None
        return (
            self._get_private_repo_releases(repository, repo_releases) if repository.private
            else self._get_public_repo_releases(repository, repo_releases)
        )

    def _get_public_repo_releases(self, repository, releases):
        """
        :type repository: type: github3.repos.repo.repos.ShortRepository
        :type releases: list[github3.repos.release.Release]
        :rtype: (dict) | None
        """
        return tuple({
            'url': '{url}/archive/{tag_name}.tar.gz'.format(
                url=repository.html_url.rstrip('/'),
                tag_name=item.tag_name,
            ),
            'name': item.tag_name
        } for item in releases)

    def _get_private_repo_releases(self, repository, releases):
        """
        :type repository: type: github3.repos.repo.repos.ShortRepository
        :type releases: list[github3.repos.release.Release]
        :rtype: dict
        """
        raise NotImplementedError
