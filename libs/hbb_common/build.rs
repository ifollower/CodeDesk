fn main() {
    const CODEDESK_BUILD_KEYS: &[&str] = &[
        "CODEDESK_SOURCE_URL",
        "CODEDESK_ISSUES_URL",
        "CODEDESK_WEBSITE_URL",
        "CODEDESK_DOWNLOAD_URL",
        "CODEDESK_PRIVACY_URL",
        "CODEDESK_DOCS_URL",
        "CODEDESK_DOCS_MOBILE_URL",
        "CODEDESK_DOCS_LINUX_PERMISSIONS_URL",
        "CODEDESK_DOCS_X11_URL",
        "CODEDESK_DOCS_LINUX_LOGIN_URL",
        "CODEDESK_DOCS_HEADLESS_URL",
        "CODEDESK_DOCS_WHITELIST_URL",
        "CODEDESK_API_URL",
        "CODEDESK_UPDATE_API_URL",
        "CODEDESK_RENDEZVOUS_SERVERS",
        "CODEDESK_RENDEZVOUS_PUBLIC_KEY",
    ];
    for key in CODEDESK_BUILD_KEYS {
        println!("cargo:rerun-if-env-changed={key}");
        let value = std::env::var(key).unwrap_or_default();
        assert!(
            !value.contains(['\r', '\n']),
            "{} must not contain line breaks",
            key
        );
        println!("cargo:rustc-env={key}={value}");
    }

    let out_dir = format!("{}/protos", std::env::var("OUT_DIR").unwrap());

    std::fs::create_dir_all(&out_dir).unwrap();

    protobuf_codegen::Codegen::new()
        .pure()
        .out_dir(out_dir)
        .inputs(["protos/rendezvous.proto", "protos/message.proto"])
        .include("protos")
        .customize(protobuf_codegen::Customize::default().tokio_bytes(true))
        .run()
        .expect("Codegen failed.");
}
