import Foundation
import Security

// MARK: - KeychainStore
//
// Thin actor wrapper around iOS Keychain Services for storing auth tokens.
//
// Design (per research in Audits/Full Codebase Audit 2026-04-10.md):
// - Actor-isolated to serialize concurrent access under Swift 6 strict concurrency.
// - kSecClassGenericPassword for opaque app-owned tokens.
// - kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly so background sync
//   can read the token after first unlock, but tokens never sync to iCloud
//   and never restore from backup (tenant isolation for refurbished devices).
// - SecItemDelete-before-SecItemAdd for idempotent upsert (avoids errSecDuplicateItem).
// - NO token logging — OS Logger with .private privacy level should be used elsewhere.

actor KeychainStore {
    static let shared = KeychainStore()

    private let service = "com.heymeld.app.auth"

    enum KeychainError: Error, CustomStringConvertible {
        case status(OSStatus)
        case notFound
        case invalidData

        var description: String {
            switch self {
            case .status(let status):
                return "Keychain error: \(status) (\(SecCopyErrorMessageString(status, nil) as String? ?? "unknown"))"
            case .notFound: return "Keychain item not found"
            case .invalidData: return "Keychain returned invalid data"
            }
        }
    }

    // MARK: - Keys we store

    private enum Account: String {
        case accessToken = "accessToken"
        case refreshToken = "refreshToken"
        case appleUserId = "appleUserId"
    }

    // MARK: - Public API — tokens as strings

    func saveAccessToken(_ token: String) throws {
        try saveString(token, account: .accessToken)
    }

    func readAccessToken() throws -> String {
        try readString(account: .accessToken)
    }

    func saveRefreshToken(_ token: String) throws {
        try saveString(token, account: .refreshToken)
    }

    func readRefreshToken() throws -> String {
        try readString(account: .refreshToken)
    }

    func saveAppleUserId(_ id: String) throws {
        try saveString(id, account: .appleUserId)
    }

    func readAppleUserId() throws -> String {
        try readString(account: .appleUserId)
    }

    /// Delete every item this store writes. Called on logout and on first
    /// launch (to wipe inherited Keychain from a previous install).
    func wipe() throws {
        for account in [Account.accessToken, .refreshToken, .appleUserId] {
            let query: [String: Any] = [
                kSecClass as String: kSecClassGenericPassword,
                kSecAttrService as String: service,
                kSecAttrAccount as String: account.rawValue,
            ]
            let status = SecItemDelete(query as CFDictionary)
            // errSecItemNotFound is fine — the item wasn't there to begin with
            guard status == errSecSuccess || status == errSecItemNotFound else {
                throw KeychainError.status(status)
            }
        }
    }

    /// Returns true if an access token is currently stored. Does not validate expiry.
    func hasStoredSession() -> Bool {
        do {
            _ = try readString(account: .accessToken)
            return true
        } catch {
            return false
        }
    }

    // MARK: - Private helpers

    private func saveString(_ value: String, account: Account) throws {
        guard let data = value.data(using: .utf8) else {
            throw KeychainError.invalidData
        }
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account.rawValue,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
            kSecValueData as String: data,
        ]
        // Idempotent upsert: delete first, then add.
        SecItemDelete(query as CFDictionary)
        let status = SecItemAdd(query as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw KeychainError.status(status)
        }
    }

    private func readString(account: Account) throws -> String {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account.rawValue,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        if status == errSecItemNotFound {
            throw KeychainError.notFound
        }
        guard status == errSecSuccess else {
            throw KeychainError.status(status)
        }
        guard let data = item as? Data, let value = String(data: data, encoding: .utf8) else {
            throw KeychainError.invalidData
        }
        return value
    }
}

// MARK: - First-launch wipe
//
// Keychain items survive app uninstall by default (Apple Forums thread 36442).
// This means a refurbished device could hand tokens from the previous owner
// to the new user. Call `wipeKeychainOnFirstLaunchIfNeeded()` at app startup
// BEFORE reading any tokens. The UserDefaults flag is reset on uninstall.

extension KeychainStore {
    static func wipeKeychainOnFirstLaunchIfNeeded() async {
        let key = "com.heymeld.app.hasLaunchedBefore"
        if UserDefaults.standard.bool(forKey: key) {
            return
        }
        do {
            try await KeychainStore.shared.wipe()
        } catch {
            // Non-fatal — log and continue
            Log.auth.error("First-launch Keychain wipe failed: \(error.localizedDescription)")
        }
        UserDefaults.standard.set(true, forKey: key)
    }
}
