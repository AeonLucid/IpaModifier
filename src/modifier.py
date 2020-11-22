import json
import os
import re
import shutil
import plistlib
from glob import glob
from json import JSONDecodeError


class Modifier:

    def __init__(self, ipa_file, config_file):
        self._ipa_file = ipa_file
        self._config_file = config_file
        self._config = None
        self._tmp_ipa_dir = None
        self._tmp_app_dir = None
        self._ipa_plist = None

    def _load_config(self):
        try:
            with open(self._config_file, mode='rb') as fp:
                self._config = json.load(fp)
            return True
        except JSONDecodeError:
            return False

    def _ipa_unpack(self):
        print('Unpacking IPA')

        self._tmp_ipa_dir = os.path.join(
            os.path.dirname(self._ipa_file),
            os.path.splitext(os.path.basename(self._ipa_file))[0] + '_tmp')

        shutil.unpack_archive(self._ipa_file, self._tmp_ipa_dir, format='zip')

        # Locate app dir.
        app_name = None

        for name in os.listdir(os.path.join(self._tmp_ipa_dir, 'Payload')):
            if os.path.isdir(os.path.join(self._tmp_ipa_dir, 'Payload', name)):
                app_name = name
                break

        if app_name is None:
            print('Failed to detect app name inside Payload directory.')
            return False

        self._tmp_app_dir = os.path.join(self._tmp_ipa_dir, 'Payload', app_name)

        # Parse plist.
        with open(os.path.join(self._tmp_app_dir, 'Info.plist'), 'rb') as fp:
            self._ipa_plist = plistlib.load(fp)

        return True

    def _ipa_pack(self):
        # Store updated plist.
        with open(os.path.join(self._tmp_app_dir, 'Info.plist'), 'wb') as fp:
            plistlib.dump(self._ipa_plist, fp)

        # Create ipa.
        output_ipa = self._ipa_file.replace('.ipa', '_mod.ipa')

        if os.path.exists(output_ipa):
            os.remove(output_ipa)

        output_file = shutil.make_archive(output_ipa, 'zip', self._tmp_ipa_dir)

        # Remove zip extension.
        os.rename(output_file, output_file[:-4])
        output_file = output_file[:-4]

        print('Packed IPA to %s' % os.path.basename(output_file))

        return True

    def _modify_bundle_property(self, plist_key, config_key):
        if config_key in self._config:
            config_value = self._config[config_key]

            if plist_key == 'CFBundleName' and len(config_value) >= 16:
                raise Exception('Invalid length of CFBundleName, must be < 16')

            self._ipa_plist[plist_key] = config_value

            print('- Modifying Info.plist key %-19s to %s' % (plist_key, config_value))

    def _modify_plugins(self):
        if 'plugins' not in self._config:
            return True

        for plugin in self._config['plugins']:
            plugin_name = plugin['name']
            plugin_bundle_id = plugin['bundleId']
            plugin_plist_file = os.path.join(self._tmp_app_dir, 'PlugIns', plugin_name, 'Info.plist')

            if not os.path.exists(plugin_plist_file):
                print('Plugin plist was missing %s' % plugin_name)
                return False

            with open(plugin_plist_file, 'rb') as fp:
                plugin_plist = plistlib.load(fp)

            plugin_plist['CFBundleIdentifier'] = plugin_bundle_id

            print('- Modifying plugin %s' % plugin_name)
            print('  - Info.plist key %-19s to %s' % ('CFBundleIdentifier', plugin_bundle_id))

            with open(plugin_plist_file, 'wb') as fp:
                plistlib.dump(plugin_plist, fp)

    def _modify_app_icons(self):
        if 'icons' not in self._config:
            return True

        # Delete old icons
        for file in glob(os.path.join(self._tmp_app_dir, 'AppIcon*.png')):
            os.remove(file)

        # Rename icons from "Icon Set Studio" to be compatible.
        for file in glob(os.path.join(self._config['icons'], 'AppIcon*.png')):
            icon_name = os.path.basename(file)
            icon_match = re.match('AppIcon(-ipad)?-([0-9.]+)(@(\\d+)x)?\\.png', icon_name)

            if icon_match is None:
                continue

            platform = icon_match[1] if icon_match[1] is not None else ''
            size = icon_match[2]
            scale = icon_match[4]

            updated_name = 'AppIcon%sx%s@%sx%s.png' % (size, size, scale, platform)
            updated_name = updated_name.replace('-', '~')
            updated_name = updated_name.replace('@Nonex', '')

            shutil.copy(file, os.path.join(self._tmp_app_dir, updated_name))

        # Replace Assets.car
        car_file = os.path.join(self._config['icons'], 'Assets.car')

        if os.path.exists(car_file):
            shutil.copy(car_file, os.path.join(self._tmp_app_dir, 'Assets.car'))

    def modify(self):
        if not self._load_config():
            print('Failed to parse configuration.')
            return False

        # Unzip IPA to a temp directory and parse Info.plist.
        if not self._ipa_unpack():
            print('Failed to unpack IPA.')
            return False

        # Show what IPA we have loaded.
        print('Loaded IPA %s %s v%s' % (
              self._ipa_plist['CFBundleName'],
              self._ipa_plist['CFBundleIdentifier'],
              self._ipa_plist['CFBundleShortVersionString']))

        self._modify_bundle_property('CFBundleIdentifier', 'bundleId')
        self._modify_bundle_property('CFBundleName', 'bundleName')
        self._modify_bundle_property('CFBundleDisplayName', 'bundleDisplayName')
        self._modify_plugins()
        self._modify_app_icons()

        # Repack IPA.
        if not self._ipa_pack():
            print('Failed to pack IPA.')
            return False

        return True

    def __enter__(self):
        return self

    def __exit__(self, type_, value, traceback):
        # Clean up unpacked IPA.
        # if self._tmp_ipa_dir is not None and os.path.exists(self._tmp_ipa_dir):
        #     shutil.rmtree(self._tmp_ipa_dir)
        pass
