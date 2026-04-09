import SwiftUI
import PhotosUI

// MARK: - Camera / Photo Capture View
// Uses PhotosPicker for MVP (simpler than AVFoundation).
// 3-tap flow: open sheet, pick/capture photo, confirm.
// Photo stored locally, base64 sent to backend for recognition.

struct CameraView: View {
    @Bindable var viewModel: MealsViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var selectedItem: PhotosPickerItem?
    @State private var capturedImage: UIImage?
    @State private var isRecognizing = false
    @State private var recognizedItems: [FoodItem] = []
    @State private var showConfirmation = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if let image = capturedImage {
                    // Photo captured — show preview
                    Image(uiImage: image)
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .frame(maxHeight: 300)
                        .clipShape(RoundedRectangle(cornerRadius: DSRadius.md))
                        .padding(DSSpacing.xl)

                    if isRecognizing {
                        VStack(spacing: DSSpacing.md) {
                            AnimatedMascot(state: .thinking, size: 48)
                            Text("Identifying your food...")
                                .font(DSTypography.body)
                                .foregroundStyle(DSColor.Text.secondary)
                        }
                        .padding(.top, DSSpacing.xxl)
                    }
                } else {
                    // No photo yet — show picker prompt
                    VStack(spacing: DSSpacing.xxl) {
                        Spacer()

                        AnimatedMascot(state: .idle, size: 64)

                        Text("Take a photo of your meal")
                            .font(DSTypography.h2)
                            .foregroundStyle(DSColor.Text.primary)

                        Text("Your coach will identify the food\nand estimate nutrition.")
                            .font(DSTypography.bodySM)
                            .foregroundStyle(DSColor.Text.secondary)
                            .multilineTextAlignment(.center)

                        PhotosPicker(
                            selection: $selectedItem,
                            matching: .images,
                            photoLibrary: .shared()
                        ) {
                            HStack(spacing: DSSpacing.sm) {
                                Image(systemName: "camera")
                                Text("Choose Photo")
                            }
                            .font(DSTypography.body.weight(.medium))
                            .foregroundStyle(.white)
                            .frame(maxWidth: .infinity)
                            .frame(height: 48)
                            .background(DSColor.Purple.purple500)
                            .clipShape(RoundedRectangle(cornerRadius: DSRadius.md))
                        }
                        .padding(.horizontal, DSSpacing.xl)

                        Spacer()
                    }
                }

                Spacer()
            }
            .background(DSColor.Background.primary)
            .navigationTitle("Log Food")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
            .onChange(of: selectedItem) { _, newItem in
                guard let newItem else { return }
                Task {
                    if let data = try? await newItem.loadTransferable(type: Data.self),
                       let image = UIImage(data: data) {
                        capturedImage = image
                        await recognizeFood(imageData: data)
                    }
                }
            }
            .sheet(isPresented: $showConfirmation) {
                FoodConfirmationView(
                    items: $recognizedItems,
                    mealType: .fromTime(Date()),
                    viewModel: viewModel,
                    image: capturedImage
                )
            }
        }
    }

    private func recognizeFood(imageData: Data) async {
        isRecognizing = true
        do {
            let items = try await APIClient.shared.recognizeFood(imageData: imageData)
            recognizedItems = items
            isRecognizing = false
            showConfirmation = true
        } catch {
            isRecognizing = false
            // Fallback: show empty confirmation so user can manually enter
            recognizedItems = []
            showConfirmation = true
        }
    }
}
