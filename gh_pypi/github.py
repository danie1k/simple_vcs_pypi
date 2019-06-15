import collections

from github3 import (  # pylint:disable=unused-import
    GitHub as GitHubApi,
    exceptions as gh_exc,
    repos,
    search,
    structs,
    users,
)
from werkzeug import exceptions

__all__ = (
    'Organization',
    'User',
)

Organization = collections.namedtuple('Organization', 'name')
User = collections.namedtuple('User', 'name')


class ConflictingRepositoriesError(exceptions.ServiceUnavailable):
    def get_description(self, environ=None):
        # pylint:disable=access-member-before-definition,attribute-defined-outside-init
        if not isinstance(self.description, str):
            self.description = 'Duplicated repository names found:\n{}'.format(
                ''.join(
                    '- "{name}" in: {locations}\n'.format(
                        name=name,
                        locations=', '.join(item.full_name for item in repo_list)
                    )
                    for name, repo_list in self.description
                )
            )
        return '<div style="white-space:pre;">{}</div>'.format(super().get_description(environ))


# noinspection SpellCheckingInspection
class GitHub:
    github_api = None  # type: GitHubApi
    current_user = None  # type: users.AuthenticatedUser

    def get_installable_repositories(self, *users_and_organizations):
        """
        :type users_and_organizations: Organization or User
        :rtype: dict[repos.ShortRepository]
        :raises werkzeug.exceptions.BadRequest: On any GitHub API error
        """
        result = tuple()  # type: (repos.ShortRepository, ...)

        accessible_users_and_organizations = tuple([
            User(name=self.current_user.login),
            *(Organization(name=item.login) for item in self.github_api.organizations())
        ])

        result += self.get_current_user_package_repositories()

        # Methods below are able to list only public repositories
        for owner in filter(lambda item: item not in accessible_users_and_organizations, users_and_organizations):
            if isinstance(owner, Organization):
                result += self.get_organization_package_repositories(owner.name)
            elif isinstance(owner, User):
                result += self.get_user_package_repositories(owner.name)

        self._verify_conflicting_repos(result)

        return collections.OrderedDict({
            item.name: item
            for item in sorted(result, key=lambda item: item.name.lower())
        })

    def get_current_user_package_repositories(self):
        # Get all repositories you have access on your account
        iterator = self.github_api.repositories(type='all')  # type: structs.GitHubIterator
        available_repositories = tuple(iterator)

        code_search_results = tuple(self.github_api.search_code(
            query=' '.join((
                # https://help.github.com/en/articles/searching-code
                'filename:setup.py',
                'path:/',
                *('repo:{}'.format(repo.full_name) for repo in available_repositories),
            ))
        ))  # type: (search.CodeSearchResult, ...)

        repositories = {}
        for code_result in code_search_results:
            repository = code_result.repository  # type: repos.ShortRepository
            if repository.full_name not in repositories:
                repositories[repository.full_name] = repository

        return tuple(repositories.values())

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

    def _verify_conflicting_repos(self, repositories):
        """
        :param repositories: (repos.ShortRepository, ...)
        :rtype: None
        :raises ConflictingRepositoriesError: If the same repository name is appeared more than once
        """
        checker = collections.defaultdict(list)
        for repo in repositories:
            checker[repo.name].append(repo)

        conflicts = tuple(
            filter(lambda item: len(item[1]) > 1, checker.items())
        )  # type: (str, [repos.ShortRepository, ...])

        if conflicts:
            raise ConflictingRepositoriesError(conflicts)
