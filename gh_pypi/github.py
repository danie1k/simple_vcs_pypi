from collections import (
    OrderedDict,
    namedtuple,
)

from github3.exceptions import GitHubException
from werkzeug.exceptions import BadRequest

__all__ = (
    'Organization',
    'User',
)

Organization = namedtuple('Organization', 'name')
User = namedtuple('Organization', 'name')


class GitHub:
    github_api = None  # type: github3.GitHub

    def get_installable_repositories(self, *users_and_organizations):
        """
        :type users_and_organizations: Organization or User
        :rtype: dict[github3.repos.repo.ShortRepository]
        :raises werkzeug.exceptions.BadRequest: On any GitHub API error
        """
        result = {}

        for owner in users_and_organizations:
            if isinstance(owner, Organization):
                result.update({repo.name: repo for repo in self.get_organization_package_repositories(owner.name)})
            elif isinstance(owner, User):
                result.update({repo.name: repo for repo in self.get_user_package_repositories(owner.name)})

        return OrderedDict(sorted(result.items(), key=lambda item: item[0].lower()))

    def get_user_package_repositories(self, username):
        """
        :type username: str
        :rtype: tuple[github3.repos.repo.ShortRepository]
        :raises werkzeug.exceptions.BadRequest: On any GitHub API error
        """
        iterator = self.github_api.search_code(
            query=' '.join((
                # https://help.github.com/en/articles/searching-code
                'filename:setup.py',
                'path:/',
                'user:{}'.format(username),
            ))
        )

        try:
            repos = tuple(iterator)  # type: tuple[github3.search.CodeSearchResult]
        except GitHubException as ex:
            raise BadRequest('Unable to get list of repositories from GitHub API') from ex

        return tuple(repo.repository for repo in repos if repo.repository.owner.login == username)

    def get_organization_package_repositories(self, organization):
        """
        :type organization: str
        :rtype: tuple[ShortRepository]
        :raises werkzeug.exceptions.BadRequest: On any GitHub API error
        """
        iterator = self.github_api.search_code(
            query=' '.join((
                # https://help.github.com/en/articles/searching-code
                'filename:setup.py',
                'path:/',
                'org:{}'.format(organization),
            ))
        )

        try:
            repos = tuple(iterator)  # type: tuple[github3.search.CodeSearchResult]
        except GitHubException as ex:
            raise BadRequest('Unable to get list of repositories from GitHub API') from ex

        return tuple(repo.repository for repo in repos if repo.repository.owner.login == organization)
