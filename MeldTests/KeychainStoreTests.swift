import Foundation
import Testing
@testable import Meld

// MARK: - KeychainStoreTests
//
// Pins the behavior the rest of the auth stack depends on:
//   AuthManager (sign-in, refresh, logout), APIClient (Bearer token),
//   MeldApp first-launch wipe, OnboardingViewModel (Apple user ID lookup).
//
// KeychainStore.shared is a singleton actor that talks to the real iOS
// Keychain service "com.heymeld.app.auth". Tests share that state, so this
// suite is .serialized and `init()` wipes before each test. Wipe is
// idempotent, so a fresh slate is guaranteed even if a prior test crashed
// without cleanup.

@Suite("KeychainStore", .serialized)
struct KeychainStoreTests {
    init() async throws {
        try await KeychainStore.shared.wipe()
    }

    // MARK: - Round-trip per account

    @Test("Access token round-trips")
    func accessTokenRoundtrips() async throws {
        try await KeychainStore.shared.saveAccessToken("access-abc")
        let read = try await KeychainStore.shared.readAccessToken()
        #expect(read == "access-abc")
    }

    @Test("Refresh token round-trips")
    func refreshTokenRoundtrips() async throws {
        try await KeychainStore.shared.saveRefreshToken("refresh-xyz")
        let read = try await KeychainStore.shared.readRefreshToken()
        #expect(read == "refresh-xyz")
    }

    @Test("Apple user ID round-trips")
    func appleUserIdRoundtrips() async throws {
        try await KeychainStore.shared.saveAppleUserId("001234.test.5678")
        let read = try await KeychainStore.shared.readAppleUserId()
        #expect(read == "001234.test.5678")
    }

    // MARK: - Account isolation
    //
    // The three accounts share one service but distinct kSecAttrAccount
    // values. Saving one must not stomp the others. This is the property
    // AuthManager relies on when it persists access + refresh + appleId
    // back-to-back inside `saveTokens(_:)`.

    @Test("Three accounts coexist independently")
    func threeAccountsCoexistIndependently() async throws {
        try await KeychainStore.shared.saveAccessToken("A")
        try await KeychainStore.shared.saveRefreshToken("R")
        try await KeychainStore.shared.saveAppleUserId("ID")
        #expect(try await KeychainStore.shared.readAccessToken() == "A")
        #expect(try await KeychainStore.shared.readRefreshToken() == "R")
        #expect(try await KeychainStore.shared.readAppleUserId() == "ID")
    }

    // MARK: - Idempotent upsert
    //
    // `saveString` does SecItemDelete-then-SecItemAdd so a second save with
    // the same account never returns errSecDuplicateItem. Token refresh
    // depends on this: AuthManager.refresh() overwrites the access token
    // every ~15 minutes for the lifetime of the install.

    @Test("Saving twice overwrites the previous value")
    func savingTwiceOverwritesPreviousValue() async throws {
        try await KeychainStore.shared.saveAccessToken("first")
        try await KeychainStore.shared.saveAccessToken("second")
        let read = try await KeychainStore.shared.readAccessToken()
        #expect(read == "second")
    }

    // MARK: - Missing item

    @Test("Reading a missing token throws .notFound")
    func readingMissingTokenThrowsNotFound() async throws {
        await #expect(throws: KeychainStore.KeychainError.self) {
            _ = try await KeychainStore.shared.readAccessToken()
        }
    }

    // MARK: - Wipe

    @Test("Wipe clears every stored item")
    func wipeClearsEveryStoredItem() async throws {
        try await KeychainStore.shared.saveAccessToken("A")
        try await KeychainStore.shared.saveRefreshToken("R")
        try await KeychainStore.shared.saveAppleUserId("ID")

        try await KeychainStore.shared.wipe()

        await #expect(throws: KeychainStore.KeychainError.self) {
            _ = try await KeychainStore.shared.readAccessToken()
        }
        await #expect(throws: KeychainStore.KeychainError.self) {
            _ = try await KeychainStore.shared.readRefreshToken()
        }
        await #expect(throws: KeychainStore.KeychainError.self) {
            _ = try await KeychainStore.shared.readAppleUserId()
        }
    }

    @Test("Wipe is safe when nothing is stored")
    func wipeIsSafeWhenNothingStored() async throws {
        // Already wiped by init(). Calling again must not throw because
        // wipe() treats errSecItemNotFound as success.
        try await KeychainStore.shared.wipe()
    }

    // MARK: - hasStoredSession

    @Test("hasStoredSession is false on a fresh keychain")
    func hasStoredSessionIsFalseOnFreshKeychain() async {
        let has = await KeychainStore.shared.hasStoredSession()
        #expect(has == false)
    }

    @Test("hasStoredSession is true after saving an access token")
    func hasStoredSessionIsTrueAfterSave() async throws {
        try await KeychainStore.shared.saveAccessToken("any")
        let has = await KeychainStore.shared.hasStoredSession()
        #expect(has == true)
    }

    @Test("hasStoredSession only checks access token, not refresh or appleId")
    func hasStoredSessionOnlyChecksAccessToken() async throws {
        // Refresh + appleId present but no access token: AppDelegate must
        // treat this as logged-out and route to onboarding, not the app.
        try await KeychainStore.shared.saveRefreshToken("R")
        try await KeychainStore.shared.saveAppleUserId("ID")
        let has = await KeychainStore.shared.hasStoredSession()
        #expect(has == false)
    }

    @Test("hasStoredSession is false again after wipe")
    func hasStoredSessionFalseAfterWipe() async throws {
        try await KeychainStore.shared.saveAccessToken("any")
        try await KeychainStore.shared.wipe()
        let has = await KeychainStore.shared.hasStoredSession()
        #expect(has == false)
    }

    // MARK: - Encoding edge cases

    @Test("UTF-8 multi-byte content round-trips byte-exact")
    func utf8MultiByteRoundtrips() async throws {
        // A real Apple user ID is ASCII, but a JWT payload or a future
        // opaque token might include non-ASCII. Pin the contract.
        let payload = "tok.\u{1F510}.\u{00E9}\u{4E2D}"
        try await KeychainStore.shared.saveAccessToken(payload)
        let read = try await KeychainStore.shared.readAccessToken()
        #expect(read == payload)
    }

    @Test("Long token (8 KB) round-trips")
    func longTokenRoundtrips() async throws {
        // JWTs with embedded claims can grow past 1 KB; the Keychain item
        // size limit is well above 8 KB but we pin a representative ceiling.
        let big = String(repeating: "x", count: 8 * 1024)
        try await KeychainStore.shared.saveAccessToken(big)
        let read = try await KeychainStore.shared.readAccessToken()
        #expect(read == big)
    }

    // MARK: - First-launch wipe helper
    //
    // Keychain items survive app uninstall (Apple Forums 36442). The helper
    // wipes once per install using a UserDefaults flag, so a refurbished
    // device can't hand the previous owner's tokens to the new user.
    //
    // These tests mutate UserDefaults.standard, so save/restore the flag
    // around the body to avoid leaking state into the simulator's defaults.

    private static let firstLaunchKey = "com.heymeld.app.hasLaunchedBefore"

    @Test("wipeKeychainOnFirstLaunchIfNeeded clears tokens and sets the flag")
    func firstLaunchHelperWipesAndSetsFlag() async throws {
        let defaults = UserDefaults.standard
        let prior = defaults.bool(forKey: Self.firstLaunchKey)
        defer { defaults.set(prior, forKey: Self.firstLaunchKey) }

        defaults.set(false, forKey: Self.firstLaunchKey)
        try await KeychainStore.shared.saveAccessToken("inherited-from-prior-install")

        await KeychainStore.wipeKeychainOnFirstLaunchIfNeeded()

        await #expect(throws: KeychainStore.KeychainError.self) {
            _ = try await KeychainStore.shared.readAccessToken()
        }
        #expect(defaults.bool(forKey: Self.firstLaunchKey) == true)
    }

    @Test("wipeKeychainOnFirstLaunchIfNeeded is a no-op when flag is set")
    func firstLaunchHelperNoOpWhenFlagSet() async throws {
        let defaults = UserDefaults.standard
        let prior = defaults.bool(forKey: Self.firstLaunchKey)
        defer { defaults.set(prior, forKey: Self.firstLaunchKey) }

        defaults.set(true, forKey: Self.firstLaunchKey)
        try await KeychainStore.shared.saveAccessToken("real-user-token")

        await KeychainStore.wipeKeychainOnFirstLaunchIfNeeded()

        // Token must still be there: this is what guarantees re-launches
        // don't sign the user out on every cold boot.
        let read = try await KeychainStore.shared.readAccessToken()
        #expect(read == "real-user-token")
    }
}
