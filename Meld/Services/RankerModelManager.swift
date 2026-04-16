import CoreML
import Foundation

// MARK: - Phase 7B CoreML model lifecycle manager
//
// Downloads the XGBoost-turned-CoreML ranker model from Cloudflare R2,
// compiles it on-device, and caches the compiled .mlmodelc in Application
// Support. The compiled model is loaded by SignalRanker for on-device
// inference when the network is unavailable.
//
// Wifi-only downloads. ETag-based conditional checks avoid re-downloading
// unchanged models. Background task scheduling is handled by AppDelegate.

actor RankerModelManager {
    static let shared = RankerModelManager()

    private let fileManager = FileManager.default

    // UserDefaults keys for cached model state.
    private let hashKey = "rankerModelHash"
    private let versionKey = "rankerModelVersion"

    private init() {}

    // MARK: - Public API

    /// Check whether a newer model is available on the server.
    /// Compares the server's file_hash against the locally cached hash.
    /// Returns true when a new model should be downloaded.
    func checkForUpdate() async throws -> Bool {
        let metadata: RankerModelMetadata
        do {
            metadata = try await APIClient.shared.fetchRankerMetadata()
        } catch {
            // 404 or network error: no model available.
            return false
        }

        let cachedHash = UserDefaults.standard.string(forKey: hashKey)
        return metadata.fileHash != cachedHash
    }

    /// Download a model from the given URL, compile it on-device, and cache
    /// the compiled .mlmodelc in Application Support. Wifi-only.
    ///
    /// Returns the URL of the compiled model directory.
    func downloadAndCompileModel(metadata: RankerModelMetadata) async throws -> URL {
        guard let downloadURL = URL(string: metadata.downloadUrl) else {
            throw RankerModelError.invalidURL
        }

        // Configure wifi-only download.
        let config = URLSessionConfiguration.default
        config.allowsCellularAccess = false
        config.timeoutIntervalForResource = 120
        let session = URLSession(configuration: config)

        let (tempURL, response) = try await session.download(from: downloadURL)

        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw RankerModelError.downloadFailed
        }

        // Move to a stable temp location with .mlmodel extension (required by compileModel).
        let stagingURL = fileManager.temporaryDirectory
            .appendingPathComponent("ranker-\(metadata.modelVersion).mlmodel")
        if fileManager.fileExists(atPath: stagingURL.path) {
            try fileManager.removeItem(at: stagingURL)
        }
        try fileManager.moveItem(at: tempURL, to: stagingURL)

        // Compile on-device.
        let compiledURL = try await MLModel.compileModel(at: stagingURL)

        // Move compiled model to permanent storage.
        let permanentURL = modelCacheDirectory()
            .appendingPathComponent("ranker.mlmodelc")

        if fileManager.fileExists(atPath: permanentURL.path) {
            try fileManager.removeItem(at: permanentURL)
        }
        try fileManager.moveItem(at: compiledURL, to: permanentURL)

        // Clean up staging file.
        try? fileManager.removeItem(at: stagingURL)

        // Save metadata to UserDefaults.
        UserDefaults.standard.set(metadata.fileHash, forKey: hashKey)
        UserDefaults.standard.set(metadata.modelVersion, forKey: versionKey)

        return permanentURL
    }

    /// URL of the cached compiled model, or nil if no model has been downloaded.
    func cachedModelURL() -> URL? {
        let url = modelCacheDirectory()
            .appendingPathComponent("ranker.mlmodelc")
        return fileManager.fileExists(atPath: url.path) ? url : nil
    }

    /// URL of the cached compiled model for loading. Callers load the model
    /// themselves to avoid sending non-Sendable MLModel across actor boundaries.
    func cachedModelURLForLoading() -> URL? {
        cachedModelURL()
    }

    /// Current cached model version, or nil.
    func cachedModelVersion() -> String? {
        UserDefaults.standard.string(forKey: versionKey)
    }

    /// Check for update and download if available. Returns true if a new
    /// model was downloaded and compiled.
    func updateIfNeeded() async -> Bool {
        do {
            let needsUpdate = try await checkForUpdate()
            guard needsUpdate else { return false }

            let metadata = try await APIClient.shared.fetchRankerMetadata()
            _ = try await downloadAndCompileModel(metadata: metadata)
            return true
        } catch {
            // Non-fatal: model update is best-effort.
            return false
        }
    }

    // MARK: - Private

    private func modelCacheDirectory() -> URL {
        let appSupport = fileManager.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first!.appendingPathComponent("Models")

        if !fileManager.fileExists(atPath: appSupport.path) {
            try? fileManager.createDirectory(
                at: appSupport,
                withIntermediateDirectories: true
            )
        }
        return appSupport
    }
}

// MARK: - Errors

enum RankerModelError: Error, LocalizedError {
    case invalidURL
    case downloadFailed
    case compilationFailed

    var errorDescription: String? {
        switch self {
        case .invalidURL: "Invalid model download URL"
        case .downloadFailed: "Model download failed"
        case .compilationFailed: "CoreML model compilation failed"
        }
    }
}
