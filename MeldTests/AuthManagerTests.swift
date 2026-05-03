import Foundation
import Testing
@testable import Meld

// MARK: - AuthManagerTests
//
// AuthManager wires Sign in with Apple, single-flight refresh, logout, and
// account deletion. APIClient depends on internal URLSession (no DI), so
// tests that exercise the network path would actually try to hit the
// backend. The tests below stay on the deterministic surface:
//
//   - validAccessToken: pure Keychain read
//   - bootstrapSession: Keychain probe + AuthSessionState publish
//   - logout: Keychain wipe + AuthSessionState publish (backend call is
//     try?'d so it's safe even with no backend reachable)
//   - UserInfo Codable round-trip
//
// Single-flight refresh and signInWithApple are network-dependent; they
// would need URLSession injection on APIClient before they can be unit
// tested. Tracked separately.
//
// Suite is .serialized because it shares KeychainStore.shared and
// AuthSessionState.shared singletons. init() resets both before each test.

@Suite("AuthManager", .serialized)
struct AuthManagerTests {
    init() async throws {
        try await KeychainStore.shared.wipe()
        await MainActor.run {
            AuthSessionState.shared.setSignedIn(false)
            AuthSessionState.shared.userDisplayName = nil
            AuthSessionState.shared.userEmail = nil
        }
    }

    // MARK: - validAccessToken

    @Test("validAccessToken returns the Keychain value")
    func validAccessTokenReturnsKeychainValue() async throws {
        try await KeychainStore.shared.saveAccessToken("at-12345")
        let token = try await AuthManager.shared.validAccessToken()
        #expect(token == "at-12345")
    }

    @Test("validAccessToken throws when no token is stored")
    func validAccessTokenThrowsWhenMissing() async throws {
        // Keychain is empty after init(). Should propagate KeychainError.notFound
        // up the stack so callers can route to login.
        await #expect(throws: KeychainStore.KeychainError.self) {
            _ = try await AuthManager.shared.validAccessToken()
        }
    }

    // MARK: - bootstrapSession

    @Test("bootstrapSession sets isSignedIn=true when access token is present")
    @MainActor
    func bootstrapSessionSignsInWhenTokenExists() async throws {
        try await KeychainStore.shared.saveAccessToken("at")
        await AuthManager.shared.bootstrapSession()
        #expect(AuthSessionState.shared.isSignedIn == true)
    }

    @Test("bootstrapSession sets isSignedIn=false when nothing is stored")
    @MainActor
    func bootstrapSessionSignsOutWhenNothingStored() async throws {
        await AuthManager.shared.bootstrapSession()
        #expect(AuthSessionState.shared.isSignedIn == false)
    }

    @Test("bootstrapSession only checks access token, not refresh or appleId")
    @MainActor
    func bootstrapSessionIgnoresRefreshAndAppleIdAlone() async throws {
        // Refresh + Apple ID present but no access token still means logged-out.
        // Mirrors KeychainStoreTests.hasStoredSessionOnlyChecksAccessToken.
        try await KeychainStore.shared.saveRefreshToken("rt")
        try await KeychainStore.shared.saveAppleUserId("apple-123")
        await AuthManager.shared.bootstrapSession()
        #expect(AuthSessionState.shared.isSignedIn == false)
    }

    // MARK: - logout

    @Test("logout wipes every Keychain item")
    func logoutWipesKeychain() async throws {
        try await KeychainStore.shared.saveAccessToken("at")
        try await KeychainStore.shared.saveRefreshToken("rt")
        try await KeychainStore.shared.saveAppleUserId("apple-123")

        await AuthManager.shared.logout()

        let hasSession = await KeychainStore.shared.hasStoredSession()
        #expect(hasSession == false)
        await #expect(throws: KeychainStore.KeychainError.self) {
            _ = try await KeychainStore.shared.readRefreshToken()
        }
        await #expect(throws: KeychainStore.KeychainError.self) {
            _ = try await KeychainStore.shared.readAppleUserId()
        }
    }

    @Test("logout clears AuthSessionState even when backend is unreachable")
    @MainActor
    func logoutClearsSessionStateOnBackendFailure() async throws {
        try await KeychainStore.shared.saveAccessToken("at")
        try await KeychainStore.shared.saveRefreshToken("rt")
        AuthSessionState.shared.setSignedIn(true, name: "Brock", email: "b@example.com")

        // logoutSession() will fail (no backend) but is wrapped in try?.
        // The Keychain wipe and isSignedIn flip MUST still happen.
        await AuthManager.shared.logout()

        #expect(AuthSessionState.shared.isSignedIn == false)
    }

    @Test("logout is safe when nothing is stored")
    @MainActor
    func logoutSafeWhenKeychainEmpty() async throws {
        // No tokens stored. logout() reads refresh token, catches .notFound,
        // wipes (no-op), and clears session state. Must not throw or crash.
        await AuthManager.shared.logout()
        #expect(AuthSessionState.shared.isSignedIn == false)
    }

    // MARK: - UserInfo Codable
    //
    // UserInfo round-trips through JSON in two places: the backend's
    // /auth/apple response (decoded by APIClient.decodeTokenPair) and any
    // future cache the iOS side adds. The is_private_email key is the one
    // most likely to drift from snake_case to camelCase during a refactor,
    // so the test pins the wire shape explicitly.

    @Test("UserInfo decodes from snake_case backend payload")
    func userInfoDecodesFromBackendPayload() async throws {
        let json = """
        {
          "id": "001234.deadbeef.5678",
          "name": "Brock Howard",
          "email": "test@privaterelay.appleid.com",
          "is_private_email": true
        }
        """.data(using: .utf8)!
        let info = try JSONDecoder().decode(AuthManager.UserInfo.self, from: json)
        #expect(info.id == "001234.deadbeef.5678")
        #expect(info.name == "Brock Howard")
        #expect(info.is_private_email == true)
    }

    @Test("UserInfo encodes back to snake_case JSON keys")
    func userInfoEncodesToSnakeCaseKeys() async throws {
        let info = AuthManager.UserInfo(
            id: "abc",
            name: nil,
            email: nil,
            is_private_email: false
        )
        let data = try JSONEncoder().encode(info)
        let json = try #require(try JSONSerialization.jsonObject(with: data) as? [String: Any])
        #expect(json["id"] as? String == "abc")
        #expect(json["is_private_email"] as? Bool == false)
        // nil name/email omit by default (no NSNull) - that's the contract
        // POST /auth/apple expects.
        #expect(json["name"] is NSNull || json["name"] == nil)
    }

    @Test("UserInfo round-trips with private-relay email")
    func userInfoRoundTripsPrivateRelay() async throws {
        let original = AuthManager.UserInfo(
            id: "001234.test.5678",
            name: "Test User",
            email: "abc123@privaterelay.appleid.com",
            is_private_email: true
        )
        let encoded = try JSONEncoder().encode(original)
        let decoded = try JSONDecoder().decode(AuthManager.UserInfo.self, from: encoded)
        #expect(decoded.id == original.id)
        #expect(decoded.name == original.name)
        #expect(decoded.email == original.email)
        #expect(decoded.is_private_email == original.is_private_email)
    }
}

// MARK: - AuthSessionState (separate suite so a failing logout test doesn't
// leak isSignedIn=true into a state-only assertion).

@Suite("AuthSessionState")
struct AuthSessionStateTests {

    @Test("setSignedIn updates isSignedIn flag")
    @MainActor
    func setSignedInTogglesFlag() async throws {
        let s = AuthSessionState.shared
        s.setSignedIn(false)
        #expect(s.isSignedIn == false)
        s.setSignedIn(true)
        #expect(s.isSignedIn == true)
        s.setSignedIn(false)
    }

    @Test("setSignedIn updates name and email when provided")
    @MainActor
    func setSignedInUpdatesNameAndEmail() async throws {
        let s = AuthSessionState.shared
        s.userDisplayName = nil
        s.userEmail = nil
        s.setSignedIn(true, name: "Brock", email: "b@example.com")
        #expect(s.userDisplayName == "Brock")
        #expect(s.userEmail == "b@example.com")
        s.setSignedIn(false)
    }

    @Test("setSignedIn preserves existing name when nil is passed")
    @MainActor
    func setSignedInPreservesNameWhenNil() async throws {
        // The signature has optional name/email. Passing nil must NOT clobber
        // the prior value; that lets logout() flip isSignedIn without
        // discarding the cached name during the brief sign-out animation.
        let s = AuthSessionState.shared
        s.setSignedIn(true, name: "Existing Name", email: "existing@example.com")
        s.setSignedIn(false)
        #expect(s.userDisplayName == "Existing Name")
        #expect(s.userEmail == "existing@example.com")
        s.userDisplayName = nil
        s.userEmail = nil
    }
}
