Name:       codedesk
Version:    1.4.9
Release:    0
Summary:    CodeDesk open-source remote workspace
License:    AGPL-3.0
Vendor:     CodeDesk Contributors
Requires:   gtk3 libxcb libXfixes alsa-lib libva2 pam gstreamer1-plugins-base
Recommends: libayatana-appindicator-gtk3 libxdo

# https://docs.fedoraproject.org/en-US/packaging-guidelines/Scriptlets/

%description
An open-source remote workspace for controlling development machines.

%prep
# we have no source, so nothing here

%build
# we have no source, so nothing here

%global __python %{__python3}

%install
mkdir -p %{buildroot}/usr/bin/
mkdir -p %{buildroot}/usr/share/codedesk/
mkdir -p %{buildroot}/usr/share/codedesk/files/
mkdir -p %{buildroot}/usr/share/icons/hicolor/256x256/apps/
mkdir -p %{buildroot}/usr/share/icons/hicolor/scalable/apps/
install -m 755 $HBB/target/release/codedesk %{buildroot}/usr/bin/codedesk
install $HBB/libsciter-gtk.so %{buildroot}/usr/share/codedesk/libsciter-gtk.so
install $HBB/res/codedesk.service %{buildroot}/usr/share/codedesk/files/
install $HBB/res/128x128@2x.png %{buildroot}/usr/share/icons/hicolor/256x256/apps/codedesk.png
install $HBB/res/scalable.svg %{buildroot}/usr/share/icons/hicolor/scalable/apps/codedesk.svg
install $HBB/res/codedesk.desktop %{buildroot}/usr/share/codedesk/files/
install $HBB/res/codedesk-link.desktop %{buildroot}/usr/share/codedesk/files/

%files
/usr/bin/codedesk
/usr/share/codedesk/libsciter-gtk.so
/usr/share/codedesk/files/codedesk.service
/usr/share/icons/hicolor/256x256/apps/codedesk.png
/usr/share/icons/hicolor/scalable/apps/codedesk.svg
/usr/share/codedesk/files/codedesk.desktop
/usr/share/codedesk/files/codedesk-link.desktop
/usr/share/codedesk/files/__pycache__/*

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
    rm /usr/share/applications/codedesk.desktop || true
    rm /usr/share/applications/codedesk-link.desktop || true
    update-desktop-database
  ;;
  1)
    # for upgrade
  ;;
esac
