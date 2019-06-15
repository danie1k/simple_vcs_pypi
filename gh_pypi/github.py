import collections

from github3 import (  # pylint:disable=unused-import
    GitHub as GitHubApi,
    exceptions as gh_exc,
    repos,
    search,
)
from werkzeug import exceptions

__all__ = (
    'Organization',
    'User',
)

Organization = collections.namedtuple('Organization', 'name')
User = collections.namedtuple('Organization', 'name')


# noinspection SpellCheckingInspection
class GitHub:
    github_api = None  # type: GitHubApi

    def get_installable_repositories(self, *users_and_organizations):
        """
        :type users_and_organizations: Organization or User
        :rtype: dict[repos.ShortRepository]
        :raises werkzeug.exceptions.BadRequest: On any GitHub API error
        """
        result = {}

        for owner in users_and_organizations:
            if isinstance(owner, Organization):
                result.update({repo.name: repo for repo in self.get_organization_package_repositories(owner.name)})
            elif isinstance(owner, User):
                result.update({repo.name: repo for repo in self.get_user_package_repositories(owner.name)})

        return collections.OrderedDict(sorted(result.items(), key=lambda item: item[0].lower()))

    def get_user_package_repositories(self, username):
        """
        :type username: str
        :rtype: (repos.ShortRepository, ...)
        :raises werkzeug.exceptions.BadRequest: On any GitHub API error
        """
        iterator = self.github_api.search_code(query=' '.join((
            # https://help.github.com/en/articles/searching-code
            'filename:setup.py',
            'path:/',
            'user:{}'.format(username),
        )))

        try:
            repositories = tuple(iterator)  # type: (search.CodeSearchResult, ...)
        except gh_exc.GitHubException as ex:
            raise exceptions.BadRequest('Unable to get list of repositories from GitHub API') from ex

        return tuple(repo.repository for repo in repositories if repo.repository.owner.login == username)

    def get_organization_package_repositories(self, organization):
        """
        :type organization: str
        :rtype: (repos.ShortRepository, ...)
        :raises werkzeug.exceptions.BadRequest: On any GitHub API error
        """
        iterator = self.github_api.search_code(query=' '.join((
            # https://help.github.com/en/articles/searching-code
            'filename:setup.py',
            'path:/',
            'org:{}'.format(organization),
        )))

        try:
            repositories = tuple(iterator)  # type: (search.CodeSearchResult, ...)
        except gh_exc.GitHubException as ex:
            raise exceptions.BadRequest('Unable to get list of repositories from GitHub API') from ex

        return tuple(repo.repository for repo in repositories if repo.repository.owner.login == organization)
