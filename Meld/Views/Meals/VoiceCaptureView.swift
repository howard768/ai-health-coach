import SwiftUI
import Speech
import AVFoundation

// MARK: - Voice Food Capture
// Uses SFSpeechRecognizer (on-device, iOS 17+) for speech-to-text.
// Transcribed text → existing food search backend → confirmation → log.
// Flow: tap mic → speak → auto-stop on silence → search → confirm → done.

struct VoiceCaptureView: View {
    @Bindable var viewModel: MealsViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var transcribedText = ""
    @State private var isListening = false
    @State private var isSearching = false
    @State private var audioLevel: Float = 0
    @State private var searchResults: [FoodItem] = []
    @State private var showConfirmation = false
    @State private var errorMessage: String?
    @State private var speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    @State private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    @State private var recognitionTask: SFSpeechRecognitionTask?
    @State private var audioEngine = AVAudioEngine()

    var body: some View {
        NavigationStack {
            VStack(spacing: DSSpacing.xxl) {
                Spacer()

                // Transcribed text display
                if !transcribedText.isEmpty {
                    Text(transcribedText)
                        .font(DSTypography.h2)
                        .foregroundStyle(DSColor.Text.primary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, DSSpacing.xl)
                } else if isListening {
                    Text("Listening...")
                        .font(DSTypography.h2)
                        .foregroundStyle(DSColor.Text.secondary)
                } else {
                    VStack(spacing: DSSpacing.lg) {
                        MeldMascot(state: .idle, size: 64)
                        Text("Say what you ate")
                            .font(DSTypography.h2)
                            .foregroundStyle(DSColor.Text.primary)
                        Text("\"I had grilled chicken with rice\nand broccoli\"")
                            .font(DSTypography.bodySM)
                            .foregroundStyle(DSColor.Text.secondary)
                            .multilineTextAlignment(.center)
                    }
                }

                if isSearching {
                    VStack(spacing: DSSpacing.md) {
                        MeldMascot(state: .thinking, size: 48)
                        Text("Looking that up...")
                            .font(DSTypography.bodySM)
                            .foregroundStyle(DSColor.Text.secondary)
                    }
                }

                Spacer()

                // Audio level indicator (simple bar animation)
                if isListening {
                    HStack(spacing: 3) {
                        ForEach(0..<12, id: \.self) { i in
                            RoundedRectangle(cornerRadius: 2)
                                .fill(DSColor.Purple.purple400)
                                .frame(width: 4, height: CGFloat.random(in: 8...max(8, CGFloat(audioLevel * 40))))
                                .animation(.easeInOut(duration: 0.1), value: audioLevel)
                        }
                    }
                    .frame(height: 40)
                }

                // Mic button
                Button {
                    if isListening {
                        stopListening()
                    } else {
                        startListening()
                    }
                } label: {
                    ZStack {
                        Circle()
                            .fill(isListening ? DSColor.Status.error : DSColor.Purple.purple500)
                            .frame(width: 72, height: 72)
                        Image(systemName: isListening ? "stop.fill" : "mic.fill")
                            .font(.system(size: 28))
                            .foregroundStyle(.white)
                    }
                }
                .disabled(isSearching)

                if let error = errorMessage {
                    Text(error)
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Status.error)
                }

                Spacer().frame(height: DSSpacing.xxl)
            }
            .background(DSColor.Background.primary)
            .navigationTitle("Voice Log")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
            .sheet(isPresented: $showConfirmation) {
                FoodConfirmationView(
                    items: $searchResults,
                    mealType: .fromTime(Date()),
                    viewModel: viewModel
                )
            }
        }
    }

    // MARK: - Speech Recognition

    private func startListening() {
        // Request permissions
        SFSpeechRecognizer.requestAuthorization { status in
            guard status == .authorized else {
                errorMessage = "Speech recognition not authorized."
                return
            }
        }

        let audioSession = AVAudioSession.sharedInstance()
        do {
            try audioSession.setCategory(.record, mode: .measurement)
            try audioSession.setActive(true, options: .notifyOthersOnDeactivation)
        } catch {
            errorMessage = "Audio session setup failed."
            return
        }

        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        guard let recognitionRequest else { return }
        recognitionRequest.shouldReportPartialResults = true
        recognitionRequest.requiresOnDeviceRecognition = true  // Privacy: on-device only

        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)

        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { buffer, _ in
            recognitionRequest.append(buffer)
            // Update audio level for visualization
            let level = buffer.floatChannelData?.pointee.pointee ?? 0
            Task { @MainActor in
                audioLevel = abs(level) * 100
            }
        }

        audioEngine.prepare()
        do {
            try audioEngine.start()
            isListening = true
        } catch {
            errorMessage = "Audio engine failed to start."
        }

        // Start recognition
        recognitionTask = speechRecognizer?.recognitionTask(with: recognitionRequest) { result, error in
            if let result {
                Task { @MainActor in
                    transcribedText = result.bestTranscription.formattedString
                }
                if result.isFinal {
                    Task { @MainActor in
                        stopListening()
                        await searchFood()
                    }
                }
            }
            if error != nil {
                Task { @MainActor in
                    stopListening()
                    if !transcribedText.isEmpty {
                        Task { await searchFood() }
                    }
                }
            }
        }

        // Auto-stop after 10 seconds
        Task {
            try? await Task.sleep(for: .seconds(10))
            if isListening {
                stopListening()
                if !transcribedText.isEmpty {
                    await searchFood()
                }
            }
        }
    }

    private func stopListening() {
        audioEngine.stop()
        audioEngine.inputNode.removeTap(onBus: 0)
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()
        isListening = false
        audioLevel = 0
    }

    private func searchFood() async {
        guard !transcribedText.isEmpty else { return }
        isSearching = true
        do {
            let results = try await APIClient.shared.searchFood(transcribedText)
            searchResults = results
            isSearching = false
            if results.isEmpty {
                errorMessage = "No results. Try again or search by name."
            } else {
                showConfirmation = true
            }
        } catch {
            isSearching = false
            errorMessage = "Search failed. Try again."
        }
    }
}
