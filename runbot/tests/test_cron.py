# -*- coding: utf-8 -*-
import os
import shutil
import subprocess
import tempfile
from unittest.mock import patch

from odoo.tests import TransactionCase
from odoo.tools import mute_logger
from odoo.addons.runbot.models.repo import CronHostError

def fake_schedule(fake_self):
    for build in fake_self:
        if build.state == 'pending':
            build.write({'state': 'testing'})

class TestCron(TransactionCase):
    def setUp(self):
        super().setUp()
        self.tmp_dir = tempfile.mkdtemp()

        @self.addCleanup
        def remove_tmp_dir():
            if os.path.isdir(self.tmp_dir):
                shutil.rmtree(self.tmp_dir)

        self.git_dir = os.path.join(self.tmp_dir, "foo")
        subprocess.check_output(['git', 'init', self.git_dir])
        self.repo = self.env["runbot.repo"].create({"name": '%s/.git' % self.git_dir})

        @self.addCleanup
        def remove_clone_dir():
            if self.repo and os.path.isdir(self.repo.path):
                shutil.rmtree(self.repo.path)

    def git(self, git_cmd):
        """ git command helper used for tests """
        cmd = ['git']
        cmd.extend(git_cmd)
        subprocess.check_output(cmd, cwd=self.git_dir)

    def test_runbot_cron(self):
        """ Test pending builds are created """
        subject = 'First commit'
        self.git(['commit', '--allow-empty', '-m', subject])
        # Test the case where the repo is not yet cloned
        with mute_logger('odoo.addons.runbot.models.repo'):
            self.repo._cron()
        self.repo._update_git()
        self.repo._cron()
        branch = self.env['runbot.branch'].search([('repo_id', '=', self.repo.id)], limit=1)
        self.assertTrue(branch)
        build = self.env['runbot.build'].search([('state', '=', 'pending')], limit=1)
        self.assertTrue(build)
        self.assertEqual(build.subject, subject)

        # check that the previous build is skipped if a newer one is found before its start
        self.git(['commit', '--allow-empty', '-m', 'A second commit'])
        self.repo._update_git()
        self.repo._cron()
        self.assertEqual(build.state, 'done')
        self.assertEqual(build.result, 'skipped')
        new_build = self.env['runbot.build'].search([('state', '=', 'pending')], limit=1)
        self.assertTrue(new_build)
        self.assertEqual(build.sequence, new_build.sequence)

    @patch('odoo.addons.runbot.models.repo.fqdn')
    @patch('odoo.addons.runbot.models.build.runbot_build._schedule', fake_schedule)
    def test_cron_for_host(self, mock_fqdn):
        """ Basic test for cron_for_host """

        branch = self.env['runbot.branch'].create({
            'repo_id': self.repo.id,
            'name': 'refs/heads/13.0'
        })
        build = self.env['runbot.build'].create({
                'branch_id': branch.id,
                'name': 'd0d0caca0000ffffffffffffffffffffffffffff',
                'subject': 'test'
        })
        # Ensure that cron is not executed if fqdn does not match
        mock_fqdn.return_value = 'runbot13.foobar.com'
        with self.assertRaises(CronHostError):
            self.repo._cron_for_host('runbot12.foobar.com')
        # now Ensure that the build is _scheduled
        mock_fqdn.return_value = 'runbot12.foobar.com'
        self.repo._cron_for_host('runbot12.foobar.com')

        self.assertEqual(build.state, 'testing')