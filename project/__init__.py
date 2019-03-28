import os.path
from glob import glob

ROOTDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATEDIR = os.path.join(ROOTDIR, 'templates')


class BaseProject(object):
    '''
    Base class storing task actions.

    Each @property method corresponds to a DoIt task of the same name.
    In practice, platformify is usually the only one that most projects will need
    to override.
    '''

    # A dictionary of conditional commands to run for package updaters.
    # The key is a file name. If that file exists, then its value will be run in the
    # project build directory to update the corresponding lock file.
    updateCommands = {
        'composer.json': 'composer update --prefer-dist --ignore-platform-reqs --no-interaction',
        'Pipfile': 'pipenv update',
        'Gemfile': 'bundle update',
        'package.json': 'npm update',
    }

    def __init__(self, name):
        self.name = name
        self.builddir = os.path.join(TEMPLATEDIR, self.name, 'build/')

        # Default: 'update'. DO NOT MODIFY except for testing purposes, then RETURN TO 'update'
        self._update_branch_name = 'tb_testing'
        # Default: 'Update to latest upstream'. DO NOT MODIFY except for testing purposes, then RETURN TO 'Update to
        #   latest upstream'
        self._commit_message = 'TEST: Do Not Merge'

    @property
    def cleanup(self):
        return ['rm -rf {0}'.format(self.builddir)]

    @property
    def init(self):
        if hasattr(self, 'github_name'):
            name = self.github_name
        else:
            name = self.name.replace('_', '-')
        return ['git clone git@github.com:platformsh/template-{0}.git {1}'.format(
            name, self.builddir)
        ]

    @property
    def update(self):
        actions = [
            'cd {0} && git checkout master && git pull --prune'.format(self.builddir)
        ]

        actions.extend(self.packageUpdateActions())

        return actions

    @property
    def platformify(self):
        """
        The default implementation of this method will
        1) Copy the contents of the files/ directory in the project over the
           application, replacing what's there.
        2) Apply any *.patch files found in the project directory, in alphabetical order.

        Individual projects may expand on these tasks as needed.
        """
        actions = ['rsync -aP {0} {1}'.format(
            os.path.join(TEMPLATEDIR, self.name, 'files/'),  self.builddir
        )]
        patches = glob(os.path.join(TEMPLATEDIR, self.name, "*.patch"))
        for patch in patches:
            actions.append('cd {0} && patch -p1 < {1}'.format(
                self.builddir, patch)
            )

        # In some cases the package updater needs to be run after we've platform-ified the
        # template, so run it a second time. Worst case it's a bit slower to build but doesn't
        # hurt anything.
        actions.extend(self.packageUpdateActions())

        return actions

    @property
    def branch(self):
        return [
            'cd {0} && if git rev-parse --verify --quiet {1}; then git checkout master && git branch -D {1}; fi;'.format(
                self.builddir, self._update_branch_name),
            'cd {0} && git checkout -b {1}'.format(self.builddir, self._update_branch_name),
            # git commit exits with 1 if there's nothing to update, so the diff-index check will
            # short circuit the command if there's nothing to update with an exit code of 0.
            'cd {0} && git add -A && git diff-index --quiet HEAD || git commit -m "{1}"'.format(
                self.builddir, self._commit_message),
        ]

    @property
    def push(self):
        return ['cd {0} && if [ `git rev-parse {1}` != `git rev-parse master` ] ; then git checkout {1} && git push --force -u origin {1}; fi'.format(
            self.builddir, self._update_branch_name)
        ]

    @property
    def pr(self):
        return ['cd {0} && hub pull-request -m "{1}"'.format(self.builddir, self._commit_message)]

    def packageUpdateActions(self):
        """
        Generates a list of package updater commands based on the updateCommands property.

        :return: List of package update commands to include.
        """
        actions = []
        for file, command in self.updateCommands.items():
            actions.append('cd {0} && [ -f {1} ] && {2} || echo "No {1} file found, skipping."'.format(self.builddir, file, command))

        return actions
