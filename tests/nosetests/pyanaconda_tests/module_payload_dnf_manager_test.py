#
# Copyright (C) 2020  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import unittest
from unittest.mock import patch, Mock

from blivet.size import Size, ROUND_UP
from pyanaconda.core.kickstart.specification import KickstartSpecificationHandler
from pyanaconda.modules.payloads.kickstart import PayloadKickstartSpecification
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManager
from pykickstart.constants import KS_BROKEN_IGNORE


class DNFMangerTestCase(unittest.TestCase):
    """Test the abstraction of the DNF base."""

    def setUp(self):
        self.maxDiff = None
        self.dnf_manager = DNFManager()

    def _check_configuration(self, *attributes):
        """Check the DNF configuration."""
        configuration = self.dnf_manager._base.conf.dump()
        configuration = configuration.splitlines(keepends=False)

        for attribute in attributes:
            self.assertIn(attribute, configuration)

    def _check_substitutions(self, substitutions):
        """Check the DNF substitutions."""
        self.assertEqual(dict(self.dnf_manager._base.conf.substitutions), substitutions)

    def create_base_test(self):
        """Test the creation of the DNF base."""
        self.assertIsNotNone(self.dnf_manager._base)

    def reset_base_test(self):
        """Test the reset of the DNF base."""
        base_1 = self.dnf_manager._base
        self.assertEqual(self.dnf_manager._base, base_1)
        self.dnf_manager.reset_base()

        base_2 = self.dnf_manager._base
        self.assertEqual(self.dnf_manager._base, base_2)
        self.assertNotEqual(self.dnf_manager._base, base_1)

    def clear_cache_test(self):
        """Test the clear_cache method."""
        self.dnf_manager.clear_cache()

    def set_default_configuration_test(self):
        """Test the default configuration of the DNF base."""
        self._check_configuration(
            "cachedir = /tmp/dnf.cache",
            "pluginconfpath = /tmp/dnf.pluginconf",
            "logdir = /tmp/",
            "debug_solver = 0",
        )
        self._check_configuration(
            "installroot = /mnt/sysroot",
            "persistdir = /mnt/sysroot/var/lib/dnf"
        )
        self._check_configuration(
            "reposdir = "
            "/etc/yum.repos.d, "
            "/etc/anaconda.repos.d, "
            "/tmp/updates/anaconda.repos.d, "
            "/tmp/product/anaconda.repos.d",
        )
        self._check_substitutions({
            "arch": "x86_64",
            "basearch": "x86_64",
            "releasever": "rawhide"
        })

    @patch("pyanaconda.modules.payloads.payload.dnf.dnf_manager.get_os_release_value")
    def set_module_platform_id_test(self, get_platform_id):
        """Test the configuration of module_platform_id."""
        get_platform_id.return_value = "platform:f32"
        self.dnf_manager.reset_base()
        self._check_configuration("module_platform_id = platform:f32")

    def configure_proxy_test(self):
        """Test the proxy configuration."""
        self.dnf_manager.configure_proxy("http://user:pass@example.com/proxy")
        self._check_configuration(
            "proxy = http://example.com:3128",
            "proxy_username = user",
            "proxy_password = pass",
        )

        self.dnf_manager.configure_proxy("@:/invalid")
        self._check_configuration(
            "proxy = ",
            "proxy_username = ",
            "proxy_password = ",
        )

        self.dnf_manager.configure_proxy("http://example.com/proxy")
        self._check_configuration(
            "proxy = http://example.com:3128",
            "proxy_username = ",
            "proxy_password = ",
        )

        self.dnf_manager.configure_proxy(None)
        self._check_configuration(
            "proxy = ",
            "proxy_username = ",
            "proxy_password = ",
        )

    def configure_base_test(self):
        """Test the configuration of the DNF base."""
        data = KickstartSpecificationHandler(
            PayloadKickstartSpecification
        )

        self.dnf_manager.configure_base(data)
        self._check_configuration(
            "multilib_policy = best",
            "timeout = 30",
            "retries = 10",
            "strict = 1",
            "install_weak_deps = 1",
        )

        data.packages.multiLib = True
        data.packages.timeout = 100
        data.packages.retries = 5
        data.packages.handleBroken = KS_BROKEN_IGNORE
        data.packages.excludeWeakdeps = True

        self.dnf_manager.configure_base(data)
        self._check_configuration(
            "multilib_policy = all",
            "timeout = 100",
            "retries = 5",
            "strict = 0",
            "install_weak_deps = 0",
        )

    def dump_configuration_test(self):
        """Test the dump of the DNF configuration."""
        with self.assertLogs(level="DEBUG") as cm:
            self.dnf_manager.dump_configuration()

        msg = "DNF configuration:"
        self.assertTrue(any(map(lambda x: msg in x, cm.output)))

        msg = "installroot = /mnt/sysroot"
        self.assertTrue(any(map(lambda x: msg in x, cm.output)))

    def get_installation_size_test(self):
        """Test the get_installation_size method."""
        # No transaction.
        size = self.dnf_manager.get_installation_size()
        self.assertEqual(size, Size("3000 MiB"))

        # Fake transaction.
        tsi_1 = Mock()
        tsi_1.pkg.installsize = 1024 * 100
        tsi_1.pkg.files = ["/file"] * 10

        tsi_2 = Mock()
        tsi_2.pkg.installsize = 1024 * 200
        tsi_2.pkg.files = ["/file"] * 20

        self.dnf_manager._base.transaction = [tsi_1, tsi_2]
        size = self.dnf_manager.get_installation_size()
        size = size.round_to_nearest("KiB", ROUND_UP)

        self.assertEqual(size, Size("528 KiB"))

    def get_download_size_test(self):
        """Test the get_download_size method."""
        # No transaction.
        size = self.dnf_manager.get_download_size()
        self.assertEqual(size, Size(0))

        # Fake transaction.
        tsi_1 = Mock()
        tsi_1.pkg.downloadsize = 1024 * 1024 * 100

        tsi_2 = Mock()
        tsi_2.pkg.downloadsize = 1024 * 1024 * 200

        self.dnf_manager._base.transaction = [tsi_1, tsi_2]
        size = self.dnf_manager.get_download_size()

        self.assertEqual(size, Size("450 MiB"))