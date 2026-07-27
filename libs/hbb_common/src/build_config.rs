//! Public CodeDesk defaults embedded at build time.
//!
//! These values are supplied by the repository build tooling. Empty values
//! deliberately disable the corresponding vendor-provided service or link.

pub const SOURCE_URL: &str = env!("CODEDESK_SOURCE_URL");
pub const ISSUES_URL: &str = env!("CODEDESK_ISSUES_URL");
pub const WEBSITE_URL: &str = env!("CODEDESK_WEBSITE_URL");
pub const DOWNLOAD_URL: &str = env!("CODEDESK_DOWNLOAD_URL");
pub const PRIVACY_URL: &str = env!("CODEDESK_PRIVACY_URL");

pub const DOCS_URL: &str = env!("CODEDESK_DOCS_URL");
pub const DOCS_MOBILE_URL: &str = env!("CODEDESK_DOCS_MOBILE_URL");
pub const DOCS_LINUX_PERMISSIONS_URL: &str = env!("CODEDESK_DOCS_LINUX_PERMISSIONS_URL");
pub const DOCS_X11_URL: &str = env!("CODEDESK_DOCS_X11_URL");
pub const DOCS_LINUX_LOGIN_URL: &str = env!("CODEDESK_DOCS_LINUX_LOGIN_URL");
pub const DOCS_HEADLESS_URL: &str = env!("CODEDESK_DOCS_HEADLESS_URL");
pub const DOCS_WHITELIST_URL: &str = env!("CODEDESK_DOCS_WHITELIST_URL");

pub const API_URL: &str = env!("CODEDESK_API_URL");
pub const UPDATE_API_URL: &str = env!("CODEDESK_UPDATE_API_URL");
pub const RENDEZVOUS_SERVERS: &str = env!("CODEDESK_RENDEZVOUS_SERVERS");
pub const RENDEZVOUS_PUBLIC_KEY: &str = env!("CODEDESK_RENDEZVOUS_PUBLIC_KEY");

pub fn rendezvous_servers() -> Vec<String> {
    parse_rendezvous_servers(RENDEZVOUS_SERVERS)
}

fn parse_rendezvous_servers(value: &str) -> Vec<String> {
    value
        .split(',')
        .map(str::trim)
        .filter(|server| !server.is_empty())
        .map(ToOwned::to_owned)
        .collect()
}

#[cfg(test)]
mod tests {
    #[test]
    fn rendezvous_servers_ignores_empty_entries_and_whitespace() {
        let servers = super::parse_rendezvous_servers(" id1.example.com, ,id2.example.com:21116 ");
        assert_eq!(servers, vec!["id1.example.com", "id2.example.com:21116"]);
    }
}
