from cachelib import FileSystemCache
from github3 import login
from github3.exceptions import AuthenticationFailed
from github3.repos.repo import ShortRepository
from werkzeug.exceptions import (
    Forbidden,
    HTTPException,
    NotFound,
    Unauthorized,
)
from werkzeug.routing import (
    Map,
    Rule,
)
from werkzeug.wrappers import (
    Request,
    Response,
)

from . import (
    github,
    templates,
)

__all__ = ('WsgiApplication', )


class WsgiApplication(github.GitHub):
    _cache = None  # type: FileSystemCache
    _urls = Map((
        Rule('/', endpoint='index'),
        Rule('/<repository_name>/', endpoint='repository'),
    ))
    _users_and_organizations = None  # type: tuple[github.Organization | github.User]
    _index_template = None  # type: str
    _repository_template = None  # type: str

    @property
    def repositories(self):
        """
        :rtype dict[github3.repos.repo.ShortRepository]
        """
        value = self._cache.get('repositories')

        if value is None:
            data = self.get_installable_repositories(*self._users_and_organizations)
            value = {key: repo._json_data for key, repo in data.items()}  # pylint:disable=protected-access
            self._cache.set('repositories', value)
            return data

        return {key: ShortRepository(json, self.github_api.session) for key, json in value.items()}

    def __init__(
        self,
        *users_and_organizations,
        cache_dir,  # Should be an absolute path!
        index_template=None,
        repository_template=None,
    ) -> None:
        """
        :type users_and_organizations: github.Organization | github.User
        :type users_and_organizations: str
        :type index_template: str
        :type repository_template: str
        :rtype: None
        """
        self._cache = FileSystemCache(cache_dir=cache_dir, default_timeout=900)
        self._users_and_organizations = users_and_organizations
        self._index_template = index_template or templates.INDEX
        self._repository_template = repository_template or templates.REPOSITORY

    def __call__(self, environ, start_response):
        """
        :type environ: dict
        :type start_response: werkzeug.serving.WSGIRequestHandler.start_response
        :rtype: werkzeug.wsgi.ClosingIterator
        """
        request = Request(environ)
        try:
            auth = self._get_authorization(request)
            self._authorize_github(auth.get('username'), auth.get('password'))

            adapter = self._urls.bind_to_environ(request.environ)
            endpoint, values = adapter.match()

            func_name = 'dispatch_{}'.format(endpoint)
            response = getattr(self, func_name)(request, **values) if hasattr(self, func_name) else NotFound()
        except HTTPException as ex:
            response = ex

        return response(environ, start_response)

    def _authorize_github(self, username, password):
        """
        :type username: str
        :type password: str
        :rtype: None
        """
        self.github_api = login(username=username, password=password)

        try:
            if self.github_api.me() is None:
                raise Forbidden()
        except AuthenticationFailed:
            raise Forbidden()

    def _get_authorization(self, request):
        """
        :type request: werkzeug.wrappers.request.Request
        :rtype: dict[str]
        """
        auth = request.authorization

        if not (auth.get('username', None) and auth.get('password', None)):
            raise Unauthorized(www_authenticate='Basic realm=\'Simple index\'')

        return auth

    def dispatch_index(self, request):  # pylint:disable=unused-argument
        """
        :type request: werkzeug.wrappers.request.Request
        :rtype: werkzeug.wrappers.response.Response
        """
        return Response(
            self._index_template % {
                'links':
                    '\n'.join('<a href="%(name)s/">%(name)s</a>' % {'name': repo} for repo in self.repositories.keys()),
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
            repository = self.repositories[repository_name]  # type: github3.repos.repo.ShortRepository
        except KeyError:
            raise NotFound()

        releases = self._get_repo_releases(repository)
        if not releases:
            return Response('No releases available for this repository', mimetype='text/html')

        return Response(
            self._repository_template % {
                'repository_name': repository.name,
                'links': '\n'.join('<a href="%(url)s">%(name)s</a>' % item for item in releases),
            },
            mimetype='text/html',
        )

    def _get_repo_releases(self, repository):
        """
        :type repository: type: github3.repos.repo.ShortRepository
        :rtype: tuple[dict] | None
        """
        repo_releases = sorted(
            repository.releases(), key=lambda item: item.created_at
        )  # type: list[github3.repos.release.Release]
        if not repo_releases:
            return None
        return (
            self._get_private_repo_releases(repository, repo_releases)
            if repository.private else self._get_public_repo_releases(repository, repo_releases)
        )

    def _get_public_repo_releases(self, repository, releases):
        """
        :type repository: type: github3.repos.repo.ShortRepository
        :type releases: list[github3.repos.release.Release]
        :rtype: tuple[dict] | None
        """
        return tuple({
            'url':
                '{url}/archive/{tag_name}.tar.gz'
                .format(url=repository.html_url.rstrip('/'), tag_name=release.tag_name),
            'name':
                release.tag_name
        } for release in releases)

    def _get_private_repo_releases(self, repository, releases):
        """
        :type repository: type: github3.repos.repo.ShortRepository
        :type releases: list[github3.repos.release.Release]
        :rtype: dict
        """
        raise NotImplementedError
