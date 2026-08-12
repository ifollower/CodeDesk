#!/usr/bin/env python3

import os
import pathlib
import platform
import zipfile
import urllib.request
import shutil
import hashlib
import argparse
import shlex
import subprocess
import sys
from pathlib import Path

windows = platform.platform().startswith('Windows')
osx = platform.platform().startswith(
    'Darwin') or platform.platform().startswith("macOS")
hbb_name = 'codedesk' + ('.exe' if windows else '')
exe_path = 'target/release/' + hbb_name
if windows:
    win_arch = 'arm64' if platform.machine().lower() in ('arm64', 'aarch64') else 'x64'
    flutter_build_dir = f'build/windows/{win_arch}/runner/Release/'
elif osx:
    flutter_build_dir = 'build/macos/Build/Products/Release/'
else:
    flutter_build_dir = 'build/linux/x64/release/bundle/'
flutter_build_dir_2 = f'flutter/{flutter_build_dir}'
skip_cargo = False
python_cmd = os.environ.get('PYTHON', 'python3')
flutter_cmd = os.environ.get('FLUTTER', 'flutter')
flutter_version = '3.24.5'
flutter_rust_bridge_codegen_version = '1.80.1'
CODEDESK_BUILD_KEYS = (
    'CODEDESK_SOURCE_URL',
    'CODEDESK_ISSUES_URL',
    'CODEDESK_WEBSITE_URL',
    'CODEDESK_DOWNLOAD_URL',
    'CODEDESK_PRIVACY_URL',
    'CODEDESK_DOCS_URL',
    'CODEDESK_DOCS_MOBILE_URL',
    'CODEDESK_DOCS_LINUX_PERMISSIONS_URL',
    'CODEDESK_DOCS_X11_URL',
    'CODEDESK_DOCS_LINUX_LOGIN_URL',
    'CODEDESK_DOCS_HEADLESS_URL',
    'CODEDESK_DOCS_WHITELIST_URL',
    'CODEDESK_API_URL',
    'CODEDESK_UPDATE_API_URL',
    'CODEDESK_RENDEZVOUS_SERVERS',
    'CODEDESK_RENDEZVOUS_PUBLIC_KEY',
)


def get_deb_arch() -> str:
    custom_arch = os.environ.get("DEB_ARCH")
    if custom_arch is None:
        return "amd64"
    return custom_arch

def get_deb_extra_depends() -> str:
    custom_arch = os.environ.get("DEB_ARCH")
    if custom_arch == "armhf": # for arm32v7 libsciter-gtk.so
        return ", libatomic1"
    return ""

def system2(cmd):
    exit_code = os.system(cmd)
    if exit_code != 0:
        sys.stderr.write(f"Error occurred when executing: `{cmd}`. Exiting.\n")
        sys.exit(-1)


def run_command(command, *, cwd=None, env=None):
    result = subprocess.run(command, cwd=cwd, env=env, check=False)
    if result.returncode != 0:
        sys.stderr.write(
            f"Error occurred when executing: {subprocess.list2cmdline(command)}. Exiting.\n"
        )
        sys.exit(-1)


def flutter_build_define_args():
    return [
        f'--dart-define={key}={os.environ.get(key, "")}'
        for key in CODEDESK_BUILD_KEYS
    ]


def resolve_flutter_command(command=None):
    configured = command or flutter_cmd
    resolved = shutil.which(configured)
    if resolved is None:
        sys.stderr.write(
            f'Flutter SDK not found: {configured}. Install Flutter {flutter_version} '
            'and make sure its bin directory is in PATH.\n'
        )
        sys.exit(-1)
    return resolved


def generate_flutter_bridge():
    global flutter_cmd
    codegen = os.environ.get('FLUTTER_RUST_BRIDGE_CODEGEN')
    if codegen:
        codegen_path = Path(codegen).expanduser()
    else:
        codegen_path = Path.home() / '.cargo/bin/flutter_rust_bridge_codegen'

    installed_version = ''
    if codegen_path.is_file():
        result = subprocess.run(
            [str(codegen_path), '--version'],
            check=False,
            capture_output=True,
            text=True,
        )
        installed_version = f'{result.stdout} {result.stderr}'

    if flutter_rust_bridge_codegen_version not in installed_version:
        if codegen:
            sys.stderr.write(
                f'{codegen_path} is not flutter_rust_bridge_codegen '
                f'{flutter_rust_bridge_codegen_version}.\n'
            )
            sys.exit(-1)
        system2(
            'cargo install flutter_rust_bridge_codegen '
            f'--version {flutter_rust_bridge_codegen_version} '
            '--features uuid --locked --force'
        )

    flutter_path = resolve_flutter_command()
    # Keep the resolved executable for all later platform build steps. On
    # Windows this preserves the .bat/.cmd suffix found through PATHEXT.
    flutter_cmd = flutter_path

    version_result = subprocess.run(
        [flutter_path, '--version', '--machine'],
        check=False,
        capture_output=True,
        text=True,
    )
    expected_version = f'"frameworkVersion": "{flutter_version}"'
    if version_result.returncode != 0 or expected_version not in version_result.stdout:
        sys.stderr.write(
            f'Flutter {flutter_version} is required for this project; '
            f'{flutter_path} reports a different version.\n'
        )
        sys.exit(-1)

    run_command([flutter_path, 'pub', 'get'], cwd='flutter')
    codegen_env = os.environ.copy()
    codegen_env['PATH'] = os.pathsep.join(
        [str(Path(flutter_path).parent), codegen_env.get('PATH', '')]
    )
    codegen_env['RUST_LOG'] = 'info'
    run_command(
        [
            str(codegen_path),
            '--rust-input', './src/flutter_ffi.rs',
            '--dart-output', './flutter/lib/generated_bridge.dart',
            '--c-output', './flutter/macos/Runner/bridge_generated.h',
            '--class-name', 'Rustdesk',
        ],
        env=codegen_env,
    )


def get_version():
    with open("Cargo.toml", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("version"):
                return line.replace("version", "").replace("=", "").replace('"', '').strip()
    return ''


def parse_rc_features(feature):
    available_features = {}
    apply_features = {}
    if not feature:
        feature = []

    def platform_check(platforms):
        if windows:
            return 'windows' in platforms
        elif osx:
            return 'osx' in platforms
        else:
            return 'linux' in platforms

    def get_all_features():
        features = []
        for (feat, feat_info) in available_features.items():
            if platform_check(feat_info['platform']):
                features.append(feat)
        return features

    if isinstance(feature, str) and feature.upper() == 'ALL':
        return get_all_features()
    elif isinstance(feature, list):
        if windows:
            # download third party is deprecated, we use github ci instead.
            # feature.append('PrivacyMode')
            pass
        for feat in feature:
            if isinstance(feat, str) and feat.upper() == 'ALL':
                return get_all_features()
            if feat in available_features:
                if platform_check(available_features[feat]['platform']):
                    apply_features[feat] = available_features[feat]
            else:
                print(f'Unrecognized feature {feat}')
        return apply_features
    else:
        raise Exception(f'Unsupported features param {feature}')


def make_parser():
    parser = argparse.ArgumentParser(description='Build script.')
    parser.add_argument(
        '-f',
        '--feature',
        dest='feature',
        metavar='N',
        type=str,
        nargs='+',
        default='',
        help='Integrate features, windows only.'
             'Available: [Not used for now]. Special value is "ALL" and empty "". Default is empty.')
    parser.add_argument('--flutter', action='store_true',
                        help='Build flutter package', default=False)
    parser.add_argument(
        '--hwcodec',
        action='store_true',
        help='Enable feature hwcodec' + (
            '' if windows or osx else ', need libva-dev.')
    )
    parser.add_argument(
        '--vram',
        action='store_true',
        help='Enable feature vram, only available on windows now.'
    )
    parser.add_argument(
        '--portable',
        action='store_true',
        help='Build windows portable'
    )
    parser.add_argument(
        '--unix-file-copy-paste',
        action='store_true',
        help='Build with unix file copy paste feature'
    )
    parser.add_argument(
        '--skip-cargo',
        action='store_true',
        help='Skip cargo build process, only flutter version + Linux supported currently'
    )
    if windows:
        parser.add_argument(
            '--skip-portable-pack',
            action='store_true',
            help='Skip packing, only flutter version + Windows supported'
        )
    parser.add_argument(
        "--package",
        type=str
    )
    if osx:
        parser.add_argument(
            '--screencapturekit',
            action='store_true',
            help='Enable feature screencapturekit'
        )
    return parser


# Generate build script for docker
#
# it assumes all build dependencies are installed in environments
# Note: do not use it in bare metal, or may break build environments
def generate_build_script_for_docker():
    with open("/tmp/build.sh", "w") as f:
        f.write('''
            #!/bin/bash
            # environment
            export CPATH="$(clang -v 2>&1 | grep "Selected GCC installation: " | cut -d' ' -f4-)/include"
            # flutter
            pushd /opt
            wget https://storage.googleapis.com/flutter_infra_release/releases/stable/linux/flutter_linux_3.0.5-stable.tar.xz
            tar -xvf flutter_linux_3.0.5-stable.tar.xz
            export PATH=`pwd`/flutter/bin:$PATH
            popd
            # flutter_rust_bridge
            dart pub global activate ffigen --version 5.0.1
            pushd /tmp && git clone https://github.com/SoLongAndThanksForAllThePizza/flutter_rust_bridge --depth=1 && popd
            pushd /tmp/flutter_rust_bridge/frb_codegen && cargo install --path . --locked && popd
            pushd flutter && flutter pub get && popd
            ~/.cargo/bin/flutter_rust_bridge_codegen --rust-input ./src/flutter_ffi.rs --dart-output ./flutter/lib/generated_bridge.dart
            # install vcpkg
            pushd /opt
            export VCPKG_ROOT=`pwd`/vcpkg
            git clone https://github.com/microsoft/vcpkg
            vcpkg/bootstrap-vcpkg.sh
            popd
            $VCPKG_ROOT/vcpkg install --x-install-root="$VCPKG_ROOT/installed"
            # build CodeDesk
            ./build.py --flutter --hwcodec
        ''')
    system2("chmod +x /tmp/build.sh")
    system2("bash /tmp/build.sh")


# Downloading third party resources is deprecated.
# We can use this function in an offline build environment.
# Even in an online environment, we recommend building third-party resources yourself.
def download_extract_features(features, res_dir):
    import re

    proxy = ''

    def req(url):
        if not proxy:
            return url
        else:
            r = urllib.request.Request(url)
            r.set_proxy(proxy, 'http')
            r.set_proxy(proxy, 'https')
            return r

    for (feat, feat_info) in features.items():
        includes = feat_info['include'] if 'include' in feat_info and feat_info['include'] else []
        includes = [re.compile(p) for p in includes]
        excludes = feat_info['exclude'] if 'exclude' in feat_info and feat_info['exclude'] else []
        excludes = [re.compile(p) for p in excludes]

        print(f'{feat} download begin')
        download_filename = feat_info['zip_url'].split('/')[-1]
        checksum_md5_response = urllib.request.urlopen(
            req(feat_info['checksum_url']))
        for line in checksum_md5_response.read().decode('utf-8').splitlines():
            if line.split()[1] == download_filename:
                checksum_md5 = line.split()[0]
                filename, _headers = urllib.request.urlretrieve(feat_info['zip_url'],
                                                                download_filename)
                md5 = hashlib.md5(open(filename, 'rb').read()).hexdigest()
                if checksum_md5 != md5:
                    raise Exception(f'{feat} download failed')
                print(f'{feat} download end. extract bein')
                zip_file = zipfile.ZipFile(filename)
                zip_list = zip_file.namelist()
                for f in zip_list:
                    file_exclude = False
                    for p in excludes:
                        if p.match(f) is not None:
                            file_exclude = True
                            break
                    if file_exclude:
                        continue

                    file_include = False if includes else True
                    for p in includes:
                        if p.match(f) is not None:
                            file_include = True
                            break
                    if file_include:
                        print(f'extract file {f}')
                        zip_file.extract(f, res_dir)
                zip_file.close()
                os.remove(download_filename)
                print(f'{feat} extract end')


def external_resources(flutter, args, res_dir):
    features = parse_rc_features(args.feature)
    if not features:
        return

    print(f'Build with features {list(features.keys())}')
    if os.path.isdir(res_dir) and not os.path.islink(res_dir):
        shutil.rmtree(res_dir)
    elif os.path.exists(res_dir):
        raise Exception(f'Find file {res_dir}, not a directory')
    os.makedirs(res_dir, exist_ok=True)
    download_extract_features(features, res_dir)
    if flutter:
        os.makedirs(flutter_build_dir_2, exist_ok=True)
        for f in pathlib.Path(res_dir).iterdir():
            print(f'{f}')
            if f.is_file():
                shutil.copy2(f, flutter_build_dir_2)
            else:
                shutil.copytree(f, f'{flutter_build_dir_2}{f.stem}')


def get_features(args):
    features = ['inline'] if not args.flutter else []
    if args.hwcodec:
        features.append('hwcodec')
    if args.vram:
        features.append('vram')
    if args.flutter:
        features.append('flutter')
    if args.unix_file_copy_paste:
        features.append('unix-file-copy-paste')
    if osx:
        if args.screencapturekit:
            features.append('screencapturekit')
    print("features:", features)
    return features


def generate_control_file(version):
    control_file_path = "../res/DEBIAN/control"
    system2('/bin/rm -rf %s' % control_file_path)

    content = """Package: codedesk
Section: net
Priority: optional
Version: %s
Architecture: %s
Maintainer: CodeDesk Contributors
Depends: libgtk-3-0t64 | libgtk-3-0, libxcb-randr0, libxdo3 | libxdo4, libxfixes3, libxcb-shape0, libxcb-xfixes0, libasound2t64 | libasound2, libsystemd0, curl, libva2, libva-drm2, libva-x11-2, libgstreamer-plugins-base1.0-0, libpam0g, gstreamer1.0-pipewire%s
Recommends: libayatana-appindicator3-1
Description: CodeDesk open-source remote workspace.

""" % (version, get_deb_arch(), get_deb_extra_depends())
    file = open(control_file_path, "w")
    file.write(content)
    file.close()


def ffi_bindgen_function_refactor():
    # workaround ffigen
    system2(
        'sed -i "s/ffi.NativeFunction<ffi.Bool Function(DartPort/ffi.NativeFunction<ffi.Uint8 Function(DartPort/g" flutter/lib/generated_bridge.dart')


def build_flutter_deb(version, features):
    if not skip_cargo:
        system2(f'cargo build --locked --features {features} --lib --release')
        ffi_bindgen_function_refactor()
    os.chdir('flutter')
    run_command(
        [flutter_cmd, 'build', 'linux', '--release', *flutter_build_define_args()]
    )
    system2('mkdir -p tmpdeb/usr/bin/')
    system2('mkdir -p tmpdeb/usr/share/codedesk')
    system2('mkdir -p tmpdeb/etc/codedesk/')
    system2('mkdir -p tmpdeb/etc/pam.d/')
    system2('mkdir -p tmpdeb/usr/share/codedesk/files/systemd/')
    system2('mkdir -p tmpdeb/usr/share/icons/hicolor/256x256/apps/')
    system2('mkdir -p tmpdeb/usr/share/icons/hicolor/scalable/apps/')
    system2('mkdir -p tmpdeb/usr/share/applications/')
    system2('mkdir -p tmpdeb/usr/share/polkit-1/actions')
    system2('rm tmpdeb/usr/bin/codedesk || true')
    system2(
        f'cp -r {flutter_build_dir}/* tmpdeb/usr/share/codedesk/')
    system2(
        'cp ../res/codedesk.service tmpdeb/usr/share/codedesk/files/systemd/')
    system2(
        'cp ../res/128x128@2x.png tmpdeb/usr/share/icons/hicolor/256x256/apps/codedesk.png')
    system2(
        'cp ../res/scalable.svg tmpdeb/usr/share/icons/hicolor/scalable/apps/codedesk.svg')
    system2(
        'cp ../res/codedesk.desktop tmpdeb/usr/share/applications/codedesk.desktop')
    system2(
        'cp ../res/codedesk-link.desktop tmpdeb/usr/share/applications/codedesk-link.desktop')
    system2(
        'cp ../res/startwm.sh tmpdeb/etc/codedesk/')
    system2(
        'cp ../res/xorg.conf tmpdeb/etc/codedesk/')
    system2(
        'cp ../res/pam.d/codedesk.debian tmpdeb/etc/pam.d/codedesk')
    system2(
        "echo \"#!/bin/sh\" >> tmpdeb/usr/share/codedesk/files/polkit && chmod a+x tmpdeb/usr/share/codedesk/files/polkit")

    system2('mkdir -p tmpdeb/DEBIAN')
    generate_control_file(version)
    system2('cp -a ../res/DEBIAN/* tmpdeb/DEBIAN/')
    md5_file_folder("tmpdeb/")
    system2('dpkg-deb -b tmpdeb codedesk.deb;')

    system2('/bin/rm -rf tmpdeb/')
    system2('/bin/rm -rf ../res/DEBIAN/control')
    os.rename('codedesk.deb', '../codedesk-%s.deb' % version)
    os.chdir("..")


def build_deb_from_folder(version, binary_folder):
    os.chdir('flutter')
    system2('mkdir -p tmpdeb/usr/bin/')
    system2('mkdir -p tmpdeb/usr/share/codedesk')
    system2('mkdir -p tmpdeb/usr/share/codedesk/files/systemd/')
    system2('mkdir -p tmpdeb/usr/share/icons/hicolor/256x256/apps/')
    system2('mkdir -p tmpdeb/usr/share/icons/hicolor/scalable/apps/')
    system2('mkdir -p tmpdeb/usr/share/applications/')
    system2('mkdir -p tmpdeb/usr/share/polkit-1/actions')
    system2('rm tmpdeb/usr/bin/codedesk || true')
    system2(
        f'cp -r ../{binary_folder}/* tmpdeb/usr/share/codedesk/')
    system2(
        'cp ../res/codedesk.service tmpdeb/usr/share/codedesk/files/systemd/')
    system2(
        'cp ../res/128x128@2x.png tmpdeb/usr/share/icons/hicolor/256x256/apps/codedesk.png')
    system2(
        'cp ../res/scalable.svg tmpdeb/usr/share/icons/hicolor/scalable/apps/codedesk.svg')
    system2(
        'cp ../res/codedesk.desktop tmpdeb/usr/share/applications/codedesk.desktop')
    system2(
        'cp ../res/codedesk-link.desktop tmpdeb/usr/share/applications/codedesk-link.desktop')
    system2(
        "echo \"#!/bin/sh\" >> tmpdeb/usr/share/codedesk/files/polkit && chmod a+x tmpdeb/usr/share/codedesk/files/polkit")

    system2('mkdir -p tmpdeb/DEBIAN')
    generate_control_file(version)
    system2('cp -a ../res/DEBIAN/* tmpdeb/DEBIAN/')
    md5_file_folder("tmpdeb/")
    system2('dpkg-deb -b tmpdeb codedesk.deb;')

    system2('/bin/rm -rf tmpdeb/')
    system2('/bin/rm -rf ../res/DEBIAN/control')
    os.rename('codedesk.deb', '../codedesk-%s.deb' % version)
    os.chdir("..")


def build_flutter_dmg(version, features):
    if not skip_cargo:
        # Keep the Rust dylib target aligned with the Flutter macOS project.
        system2(
            f'MACOSX_DEPLOYMENT_TARGET=10.14 cargo build --locked --features {features} --release')
    # copy dylib
    system2(
        "cp target/release/liblibrustdesk.dylib target/release/librustdesk.dylib")
    os.chdir('flutter')
    # cargo builds a single-arch dylib for the host; restrict Xcode to the same arch
    # so the universal-by-default ARCHS_STANDARD doesn't try to link a missing slice.
    # FLUTTER_XCODE_* env vars are forwarded to xcodebuild as build settings.
    mac_arch = 'arm64' if platform.machine().lower() in ('arm64', 'aarch64') else 'x86_64'
    run_command([flutter_cmd, 'clean'])
    flutter_env = os.environ.copy()
    flutter_env['FLUTTER_XCODE_ARCHS'] = mac_arch
    flutter_env['FLUTTER_XCODE_ONLY_ACTIVE_ARCH'] = 'YES'
    run_command(
        [flutter_cmd, 'build', 'macos', '--release', *flutter_build_define_args()],
        env=flutter_env,
    )
    app_path = Path('build/macos/Build/Products/Release/CodeDesk.app')
    system2(f'cp -rf ../target/release/service {shlex.quote(str(app_path / "Contents/MacOS/"))}')

    # Adding the service after Xcode has signed the bundle invalidates the app
    # seal. Re-sign the complete local package without hardened runtime: an
    # ad-hoc signature has no Team ID, so library validation would otherwise
    # reject the bundled Flutter frameworks on launch.
    entitlements_path = Path('macos/Runner/Release.entitlements')
    system2(
        f'codesign --force --deep --sign - '
        f'--entitlements {shlex.quote(str(entitlements_path))} '
        f'{shlex.quote(str(app_path))}'
    )
    system2(
        f'codesign --verify --deep --strict --verbose=1 '
        f'{shlex.quote(str(app_path))}'
    )

    dmg_stage = Path('build/macos/dmg')
    if dmg_stage.exists():
        shutil.rmtree(dmg_stage)
    dmg_stage.mkdir(parents=True)
    shutil.copytree(app_path, dmg_stage / 'CodeDesk.app', symlinks=True)
    os.symlink('/Applications', dmg_stage / 'Applications')

    package_dir = Path('../target/packages')
    package_dir.mkdir(parents=True, exist_ok=True)
    dmg_path = package_dir / f'codedesk-{version}-macos-{mac_arch}.dmg'
    if dmg_path.exists():
        dmg_path.unlink()
    system2(
        f'hdiutil create -volname CodeDesk -srcfolder {shlex.quote(str(dmg_stage))} '
        f'-ov -format UDZO {shlex.quote(str(dmg_path))}'
    )
    print(f'output location: {dmg_path.resolve()}')
    os.chdir("..")


def build_flutter_arch_manjaro(version, features):
    if not skip_cargo:
        system2(f'cargo build --locked --features {features} --lib --release')
    ffi_bindgen_function_refactor()
    os.chdir('flutter')
    run_command(
        [flutter_cmd, 'build', 'linux', '--release', *flutter_build_define_args()]
    )
    system2(f'strip {flutter_build_dir}/lib/librustdesk.so')
    os.chdir('../res')
    system2('HBB=`pwd`/.. FLUTTER=1 makepkg -f')


def sign_flutter_windows_bundle():
    if os.environ.get('CODEDESK_SIGN_WINDOWS_BUNDLE') != '1':
        return
    pfx = os.environ.get('WINDOWS_SIGNING_PFX', '')
    password = os.environ.get('WINDOWS_SIGNING_PASSWORD', '')
    timestamp = os.environ.get(
        'WINDOWS_TIMESTAMP_URL', 'http://timestamp.digicert.com')
    signtool = shutil.which(os.environ.get('SIGNTOOL', 'signtool'))
    if not pfx or not os.path.isfile(pfx) or not password or not signtool:
        sys.stderr.write(
            'Windows bundle signing requires signtool, WINDOWS_SIGNING_PFX, '
            'and WINDOWS_SIGNING_PASSWORD.\n')
        sys.exit(-1)

    bundle = Path(flutter_build_dir_2)
    binaries = sorted(
        path for path in bundle.rglob('*')
        if path.is_file() and path.suffix.lower() in ('.exe', '.dll')
    )
    for binary in binaries:
        result = subprocess.run(
            [
                signtool, 'sign',
                '/fd', 'SHA256',
                '/td', 'SHA256',
                '/tr', timestamp,
                '/f', pfx,
                '/p', password,
                str(binary),
            ],
            check=False,
        )
        if result.returncode != 0:
            sys.stderr.write(f'Failed to sign Windows bundle file: {binary}\n')
            sys.exit(-1)


def build_flutter_windows(version, features, skip_portable_pack):
    if not skip_cargo:
        system2(f'cargo build --locked --features {features} --lib --release')
        if not os.path.exists("target/release/librustdesk.dll"):
            print("cargo build failed, please check rust source code.")
            exit(-1)
    os.chdir('flutter')
    run_command([flutter_cmd, 'clean'])
    run_command(
        [flutter_cmd, 'build', 'windows', '--release', *flutter_build_define_args()]
    )
    os.chdir('..')
    shutil.copy2('target/release/deps/dylib_virtual_display.dll',
                 flutter_build_dir_2)
    sign_flutter_windows_bundle()
    if skip_portable_pack:
        return
    os.chdir('libs/portable')
    run_command([python_cmd, '-m', 'pip', 'install', '-r', 'requirements.txt'])
    run_command([
        python_cmd,
        './generate.py',
        '-f', f'../../{flutter_build_dir_2}',
        '-o', '.',
        '-e', f'../../{flutter_build_dir_2}/codedesk.exe',
    ])
    os.chdir('../..')
    if os.path.exists('./codedesk_portable.exe'):
        os.replace('./target/release/rustdesk-portable-packer.exe',
                   './codedesk_portable.exe')
    else:
        os.rename('./target/release/rustdesk-portable-packer.exe',
                  './codedesk_portable.exe')
    package_dir = Path('target/packages')
    package_dir.mkdir(parents=True, exist_ok=True)
    package_path = package_dir / f'codedesk-{version}-windows-{win_arch}-install.exe'
    if package_path.exists():
        package_path.unlink()
    os.replace('./codedesk_portable.exe', package_path)
    print(f'output location: {package_path.resolve()}')


def main():
    global skip_cargo
    parser = make_parser()
    args = parser.parse_args()

    if os.path.exists(exe_path):
        os.unlink(exe_path)
    if os.path.isfile('/usr/bin/pacman'):
        system2('git checkout src/ui/common.tis')
    version = get_version()
    features = ','.join(get_features(args))
    flutter = args.flutter
    if not flutter:
        system2('python3 res/inline-sciter.py')
    print(args.skip_cargo)
    if args.skip_cargo:
        skip_cargo = True
    portable = args.portable
    package = args.package
    if package:
        build_deb_from_folder(version, package)
        return
    res_dir = 'resources'
    external_resources(flutter, args, res_dir)
    if flutter:
        generate_flutter_bridge()
    if windows:
        # build virtual display dynamic library
        os.chdir('libs/virtual_display/dylib')
        system2('cargo build --locked --release')
        os.chdir('../../..')

        if flutter:
            build_flutter_windows(version, features, args.skip_portable_pack)
            return
        system2('cargo build --locked --release --features ' + features)
        # system2('upx.exe target/release/codedesk.exe')
        system2('mv target/release/codedesk.exe target/release/CodeDesk.exe')
        pa = os.environ.get('P')
        if pa:
            # https://certera.com/kb/tutorial-guide-for-safenet-authentication-client-for-code-signing/
            system2(
                f'signtool sign /a /v /p {pa} /debug /f .\\cert.pfx /t http://timestamp.digicert.com  '
                'target\\release\\codedesk.exe')
        else:
            print('Not signed')
        os.makedirs(res_dir, exist_ok=True)
        system2(
            f'cp -rf target/release/CodeDesk.exe {res_dir}')
        os.chdir('libs/portable')
        system2('pip3 install -r requirements.txt')
        system2(
            f'python3 ./generate.py -f ../../{res_dir} -o . -e ../../{res_dir}/codedesk-{version}-win7-install.exe')
        system2(f'mv ../../{res_dir}/codedesk-{version}-win7-install.exe ../..')
    elif os.path.isfile('/usr/bin/pacman'):
        # pacman -S -needed base-devel
        system2("sed -i 's/pkgver=.*/pkgver=%s/g' res/PKGBUILD" % version)
        if flutter:
            build_flutter_arch_manjaro(version, features)
        else:
            system2('cargo build --locked --release --features ' + features)
            system2('git checkout src/ui/common.tis')
            system2('strip target/release/codedesk')
            system2('ln -s res/pacman_install && ln -s res/PKGBUILD')
            system2('HBB=`pwd` makepkg -f')
        system2('mv codedesk-%s-0-x86_64.pkg.tar.zst codedesk-%s-manjaro-arch.pkg.tar.zst' % (
            version, version))
        # pacman -U ./codedesk.pkg.tar.zst
    elif os.path.isfile('/usr/bin/yum'):
        system2('cargo build --locked --release --features ' + features)
        system2('strip target/release/codedesk')
        system2(
            "sed -i 's/Version:    .*/Version:    %s/g' res/rpm.spec" % version)
        system2('HBB=`pwd` rpmbuild -ba res/rpm.spec')
        system2(
            'mv $HOME/rpmbuild/RPMS/x86_64/codedesk-%s-0.x86_64.rpm ./codedesk-%s-fedora28-centos8.rpm' % (
                version, version))
        # yum localinstall codedesk.rpm
    elif os.path.isfile('/usr/bin/zypper'):
        system2('cargo build --locked --release --features ' + features)
        system2('strip target/release/codedesk')
        system2(
            "sed -i 's/Version:    .*/Version:    %s/g' res/rpm-suse.spec" % version)
        system2('HBB=`pwd` rpmbuild -ba res/rpm-suse.spec')
        system2(
            'mv $HOME/rpmbuild/RPMS/x86_64/codedesk-%s-0.x86_64.rpm ./codedesk-%s-suse.rpm' % (
                version, version))
        # yum localinstall codedesk.rpm
    else:
        if flutter:
            if osx:
                build_flutter_dmg(version, features)
                pass
            else:
                # system2(
                #     'mv target/release/bundle/deb/codedesk*.deb ./flutter/codedesk.deb')
                build_flutter_deb(version, features)
        else:
            system2('cargo --locked bundle --release --features ' + features)
            if osx:
                system2(
                    'strip target/release/bundle/osx/CodeDesk.app/Contents/MacOS/codedesk')
                system2(
                    'cp libsciter.dylib target/release/bundle/osx/CodeDesk.app/Contents/MacOS/')
                # https://github.com/sindresorhus/create-dmg
                system2('/bin/rm -rf *.dmg')
                pa = os.environ.get('P')
                if pa:
                    system2('''
    # buggy: rcodesign sign ... path/*, have to sign one by one
    # install rcodesign via cargo install apple-codesign
    #rcodesign sign --p12-file ~/.p12/codedesk-developer-id.p12 --p12-password-file ~/.p12/.cert-pass --code-signature-flags runtime ./target/release/bundle/osx/CodeDesk.app/Contents/MacOS/codedesk
    #rcodesign sign --p12-file ~/.p12/codedesk-developer-id.p12 --p12-password-file ~/.p12/.cert-pass --code-signature-flags runtime ./target/release/bundle/osx/CodeDesk.app/Contents/MacOS/libsciter.dylib
    #rcodesign sign --p12-file ~/.p12/codedesk-developer-id.p12 --p12-password-file ~/.p12/.cert-pass --code-signature-flags runtime ./target/release/bundle/osx/CodeDesk.app
    # goto "Keychain Access" -> "My Certificates" for below id which starts with "Developer ID Application:"
    codesign -s "Developer ID Application: {0}" --force --options runtime  ./target/release/bundle/osx/CodeDesk.app/Contents/MacOS/*
    codesign -s "Developer ID Application: {0}" --force --options runtime  ./target/release/bundle/osx/CodeDesk.app
    '''.format(pa))
                system2(
                    'create-dmg "CodeDesk %s.dmg" "target/release/bundle/osx/CodeDesk.app"' % version)
                os.rename('CodeDesk %s.dmg' %
                          version, 'codedesk-%s.dmg' % version)
                if pa:
                    system2('''
    # https://pyoxidizer.readthedocs.io/en/apple-codesign-0.14.0/apple_codesign.html
    # https://pyoxidizer.readthedocs.io/en/stable/tugger_code_signing.html
    # https://developer.apple.com/developer-id/
    # goto xcode and login with apple id, manager certificates (Developer ID Application and/or Developer ID Installer) online there (only download and double click (install) cer file can not export p12 because no private key)
    #rcodesign sign --p12-file ~/.p12/codedesk-developer-id.p12 --p12-password-file ~/.p12/.cert-pass --code-signature-flags runtime ./codedesk-{1}.dmg
    codesign -s "Developer ID Application: {0}" --force --options runtime ./codedesk-{1}.dmg
    # https://appstoreconnect.apple.com/access/api
    # https://gregoryszorc.com/docs/apple-codesign/stable/apple_codesign_getting_started.html#apple-codesign-app-store-connect-api-key
    # p8 file is generated when you generate api key (can download only once)
    rcodesign notary-submit --api-key-path ../.p12/api-key.json  --staple codedesk-{1}.dmg
    # verify:  spctl -a -t exec -v /Applications/CodeDesk.app
    '''.format(pa, version))
                else:
                    print('Not signed')
            else:
                # build deb package
                system2(
                    'mv target/release/bundle/deb/codedesk*.deb ./codedesk.deb')
                system2('dpkg-deb -R codedesk.deb tmpdeb')
                system2('mkdir -p tmpdeb/usr/share/codedesk/files/systemd/')
                system2('mkdir -p tmpdeb/usr/share/icons/hicolor/256x256/apps/')
                system2('mkdir -p tmpdeb/usr/share/icons/hicolor/scalable/apps/')
                system2(
                    'cp res/codedesk.service tmpdeb/usr/share/codedesk/files/systemd/')
                system2(
                    'cp res/128x128@2x.png tmpdeb/usr/share/icons/hicolor/256x256/apps/codedesk.png')
                system2(
                    'cp res/scalable.svg tmpdeb/usr/share/icons/hicolor/scalable/apps/codedesk.svg')
                system2(
                    'cp res/codedesk.desktop tmpdeb/usr/share/applications/codedesk.desktop')
                system2(
                    'cp res/codedesk-link.desktop tmpdeb/usr/share/applications/codedesk-link.desktop')
                os.system('mkdir -p tmpdeb/etc/codedesk/')
                os.system('cp -a res/startwm.sh tmpdeb/etc/codedesk/')
                os.system('mkdir -p tmpdeb/etc/X11/codedesk/')
                os.system('cp res/xorg.conf tmpdeb/etc/X11/codedesk/')
                os.system('cp -a DEBIAN/* tmpdeb/DEBIAN/')
                os.system('mkdir -p tmpdeb/etc/pam.d/')
                os.system('cp res/pam.d/codedesk.debian tmpdeb/etc/pam.d/codedesk')
                system2('strip tmpdeb/usr/bin/codedesk')
                system2('mkdir -p tmpdeb/usr/share/codedesk')
                system2('mv tmpdeb/usr/bin/codedesk tmpdeb/usr/share/codedesk/')
                system2('cp libsciter-gtk.so tmpdeb/usr/share/codedesk/')
                md5_file_folder("tmpdeb/")
                system2('dpkg-deb -b tmpdeb codedesk.deb; /bin/rm -rf tmpdeb/')
                os.rename('codedesk.deb', 'codedesk-%s.deb' % version)


def md5_file(fn):
    md5 = hashlib.md5(open('tmpdeb/' + fn, 'rb').read()).hexdigest()
    system2('echo "%s  /%s" >> tmpdeb/DEBIAN/md5sums' % (md5, fn))

def md5_file_folder(base_dir):
    base_path = Path(base_dir)
    for file in base_path.rglob('*'):
        if file.is_file() and 'DEBIAN' not in file.parts:
            relative_path = file.relative_to(base_path)
            md5_file(str(relative_path))


if __name__ == "__main__":
    main()
