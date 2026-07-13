Source: codedesk-server
Section: net
Priority: optional
Maintainer: CodeDesk Contributors
Build-Depends: debhelper (>= 10), cargo, rustc, pkg-config, libssl-dev, libsodium-dev
Standards-Version: 4.5.0
Rules-Requires-Root: no

Package: codedesk-server-hbbs
Architecture: {{ ARCH }}
Depends: systemd ${misc:Depends}
Description: CodeDesk rendezvous server
 Self-host the CodeDesk ID/rendezvous and NAT traversal coordination service.

Package: codedesk-server-hbbr
Architecture: {{ ARCH }}
Depends: systemd ${misc:Depends}
Description: CodeDesk relay server
 Self-host the CodeDesk relay service.

Package: codedesk-server-utils
Architecture: {{ ARCH }}
Depends: ${misc:Depends}
Description: CodeDesk server utilities
 Administration utilities for a self-hosted CodeDesk server.
