import SwiftUI
import VisionKit

// MARK: - Barcode Scanner View
// Uses VisionKit DataScannerViewController (iOS 16+).
// Auto-captures on detection for 2-tap flow: open, auto-scan.
// Looks up product via Open Food Facts API.

struct BarcodeScannerView: View {
    @Bindable var viewModel: MealsViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var scannedCode: String?
    @State private var scannedItem: FoodItem?
    @State private var isLooking = false
    @State private var notFound = false
    @State private var showConfirmation = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if DataScannerViewController.isSupported && DataScannerViewController.isAvailable {
                    if isLooking {
                        VStack(spacing: DSSpacing.md) {
                            AnimatedMascot(state: .thinking, size: 48)
                            Text("Looking up product...")
                                .font(DSTypography.body)
                                .foregroundStyle(DSColor.Text.secondary)
                        }
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                    } else if notFound {
                        VStack(spacing: DSSpacing.md) {
                            AnimatedMascot(state: .concerned, size: 48)
                            Text("Product not found")
                                .font(DSTypography.h3)
                                .foregroundStyle(DSColor.Text.primary)
                            Text("Try searching by name instead.")
                                .font(DSTypography.bodySM)
                                .foregroundStyle(DSColor.Text.secondary)
                            DSButton(title: "Search", style: .secondary, size: .md) {
                                dismiss()
                            }
                        }
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .padding(DSSpacing.xl)
                    } else {
                        DataScannerRepresentable { code in
                            scannedCode = code
                            Task { await lookupBarcode(code) }
                        }
                    }
                } else {
                    VStack(spacing: DSSpacing.md) {
                        Text("Barcode scanning is not available on this device.")
                            .font(DSTypography.body)
                            .foregroundStyle(DSColor.Text.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .padding(DSSpacing.xl)
                }
            }
            .background(DSColor.Background.primary)
            .navigationTitle("Scan Barcode")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
            .sheet(isPresented: $showConfirmation) {
                if let item = scannedItem {
                    FoodConfirmationView(
                        items: .constant([item]),
                        mealType: .fromTime(Date()),
                        viewModel: viewModel
                    )
                }
            }
        }
    }

    private func lookupBarcode(_ code: String) async {
        isLooking = true
        do {
            if let item = try await APIClient.shared.lookupBarcode(code) {
                scannedItem = item
                isLooking = false
                showConfirmation = true
            } else {
                isLooking = false
                notFound = true
            }
        } catch {
            isLooking = false
            notFound = true
        }
    }
}

// MARK: - DataScanner UIKit Bridge

struct DataScannerRepresentable: UIViewControllerRepresentable {
    var onBarcodeScanned: (String) -> Void

    func makeUIViewController(context: Context) -> DataScannerViewController {
        let scanner = DataScannerViewController(
            recognizedDataTypes: [.barcode(symbologies: [.ean8, .ean13, .upce])],
            isHighlightingEnabled: true
        )
        scanner.delegate = context.coordinator
        try? scanner.startScanning()
        return scanner
    }

    func updateUIViewController(_ uiViewController: DataScannerViewController, context: Context) {}

    func makeCoordinator() -> Coordinator {
        Coordinator(onBarcodeScanned: onBarcodeScanned)
    }

    class Coordinator: NSObject, DataScannerViewControllerDelegate {
        var onBarcodeScanned: (String) -> Void
        private var hasScanned = false

        init(onBarcodeScanned: @escaping (String) -> Void) {
            self.onBarcodeScanned = onBarcodeScanned
        }

        func dataScanner(_ dataScanner: DataScannerViewController, didAdd addedItems: [RecognizedItem], allItems: [RecognizedItem]) {
            guard !hasScanned else { return }
            for item in addedItems {
                if case .barcode(let barcode) = item {
                    if let value = barcode.payloadStringValue {
                        hasScanned = true
                        dataScanner.stopScanning()
                        onBarcodeScanned(value)
                        return
                    }
                }
            }
        }
    }
}
