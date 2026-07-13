Name:       codedesk
Version:    1.4.9
Release:    0
Summary:    CodeDesk open-source remote workspace
License:    AGPL-3.0
Vendor:     CodeDesk Contributors
Requires:   gtk3 libxcb libXfixes alsa-lib libva pam gstreamer1-plugins-base
Recommends: libayatana-appindicator-gtk3 libxdo
Provides:   libdesktop_drop_plugin.so()(64bit), libdesktop_multi_window_plugin.so()(64bit), libfile_selector_linux_plugin.so()(64bit), libflutter_custom_cursor_plugin.so()(64bit), libflutter_linux_gtk.so()(64bit), libscreen_retriever_plugin.so()(64bit), libtray_manager_plugin.so()(64bit), liburl_launcher_linux_plugin.so()(64bit), libwindow_manager_plugin.so()(64bit), libwindow_size_plugin.so()(64bit), libtexture_rgba_renderer_plugin.so()(64bit)

# https://docs.fedoraproject.org/en-US/packaging-guidelines/Scriptlets/

%description
An open-source remote workspace for controlling development machines.

%prep
# we have no source, so nothing here

%build
# we have no source, so nothing here

# %global __python %{__python3}

%install

mkdir -p "%{buildroot}/usr/share/codedesk" && cp -r ${HBB}/flutter/build/linux/x64/release/bundle/* -t "%{buildroot}/usr/share/codedesk"
mkdir -p "%{buildroot}/usr/bin"
install -Dm 644 $HBB/res/codedesk.service -t "%{buildroot}/usr/share/codedesk/files"
install -Dm 644 $HBB/res/codedesk.desktop -t "%{buildroot}/usr/share/codedesk/files"
install -Dm 644 $HBB/res/codedesk-link.desktop -t "%{buildroot}/usr/share/codedesk/files"
install -Dm 644 $HBB/res/128x128@2x.png "%{buildroot}/usr/share/icons/hicolor/256x256/apps/codedesk.png"
install -Dm 644 $HBB/res/scalable.svg "%{buildroot}/usr/share/icons/hicolor/scalable/apps/codedesk.svg"

%files
/usr/share/codedesk/*
/usr/share/codedesk/files/codedesk.service
/usr/share/icons/hicolor/256x256/apps/codedesk.png
/usr/share/icons/hicolor/scalable/apps/codedesk.svg
/usr/share/codedesk/files/codedesk.desktop
/usr/share/codedesk/files/codedesk-link.desktop

%changelog
# let's skip this for now

%pre
# can do something for centos7
case "$1" in
  1)
    # for install
  ;;
  2)
    # for upgrade
    systemctl stop codedesk || true
  ;;
esac

%post
cp /usr/share/codedesk/files/codedesk.service /etc/systemd/system/codedesk.service
cp /usr/share/codedesk/files/codedesk.desktop /usr/share/applications/
cp /usr/share/codedesk/files/codedesk-link.desktop /usr/share/applications/
ln -sf /usr/share/codedesk/codedesk /usr/bin/codedesk
systemctl daemon-reload
systemctl enable codedesk
systemctl start codedesk
update-desktop-database

%preun
case "$1" in
  0)
    # for uninstall
    systemctl stop codedesk || true
    systemctl disable codedesk || true
    rm /etc/systemd/system/codedesk.service || true
  ;;
  1)
    # for upgrade
  ;;
esac

%postun
case "$1" in
  0)
    # for uninstall
    rm /usr/bin/codedesk || true
    rmdir /usr/lib/codedesk || true
    rmdir /usr/local/codedesk || true
    rmdir /usr/share/codedesk || true
    rm /usr/share/applications/codedesk.desktop || true
    rm /usr/share/applications/codedesk-link.desktop || true
    update-desktop-database
  ;;
  1)
    # for upgrade
    rmdir /usr/lib/codedesk || true
    rmdir /usr/local/codedesk || true
  ;;
esac
