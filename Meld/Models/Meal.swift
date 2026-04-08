import Foundation

// MARK: - Meal Data Models
// Designed for consistency: nutrition values are snapshotted at log time,
// not live references. The same food always returns the same values
// because the primary source is USDA (lab-analyzed) + Open Food Facts,
// not AI estimation.
//
// Source priority: USDA lab > USDA branded > Open Food Facts > FatSecret > AI estimate
// AI estimates are flagged so users know the confidence level.

struct Meal: Identifiable {
    let id: UUID
    let date: Date
    let mealType: MealType
    var items: [FoodItem]
    var photoURL: URL?
    var source: InputSource

    init(id: UUID = UUID(), date: Date = Date(), mealType: MealType? = nil, items: [FoodItem] = [], photoURL: URL? = nil, source: InputSource = .manual) {
        self.id = id
        self.date = date
        self.mealType = mealType ?? MealType.fromTime(date)
        self.items = items
        self.photoURL = photoURL
        self.source = source
    }

    // Computed totals
    var totalCalories: Int { items.reduce(0) { $0 + $1.calories } }
    var totalProtein: Double { items.reduce(0) { $0 + $1.protein } }
    var totalCarbs: Double { items.reduce(0) { $0 + $1.carbs } }
    var totalFat: Double { items.reduce(0) { $0 + $1.fat } }

    var overallQuality: FoodQuality {
        let qualities = items.map(\.quality)
        let wholeCount = qualities.filter { $0 == .whole }.count
        let processedCount = qualities.filter { $0 == .processed }.count
        if wholeCount > qualities.count / 2 { return .whole }
        if processedCount > qualities.count / 2 { return .processed }
        return .mixed
    }
}

enum MealType: String, CaseIterable, Identifiable {
    case breakfast = "Breakfast"
    case lunch = "Lunch"
    case dinner = "Dinner"
    case snack = "Snack"

    var id: String { rawValue }

    /// Auto-assign meal type by time of day — no unnecessary decisions
    static func fromTime(_ date: Date) -> MealType {
        let hour = Calendar.current.component(.hour, from: date)
        switch hour {
        case 5..<11: return .breakfast
        case 11..<15: return .lunch
        case 15..<17: return .snack
        case 17..<22: return .dinner
        default: return .snack
        }
    }
}

enum InputSource: String {
    case photo       // Claude Vision
    case barcode     // Open Food Facts / FatSecret lookup
    case text        // Natural language parsed by AI
    case voice       // Voice → text → AI
    case search      // Database search
    case suggestion  // Re-logged from saved meal / recent
    case manual      // Manual entry
}

struct FoodItem: Identifiable {
    let id: UUID
    let name: String
    let servingSize: String
    let servingCount: Double
    let calories: Int
    let protein: Double
    let carbs: Double
    let fat: Double
    let quality: FoodQuality
    let dataSource: FoodDataSource
    let confidence: Double    // 1.0 for database, <1.0 for AI estimates

    init(id: UUID = UUID(), name: String, servingSize: String = "1 serving", servingCount: Double = 1.0, calories: Int, protein: Double, carbs: Double, fat: Double, quality: FoodQuality = .mixed, dataSource: FoodDataSource = .usda, confidence: Double = 1.0) {
        self.id = id
        self.name = name
        self.servingSize = servingSize
        self.servingCount = servingCount
        self.calories = calories
        self.protein = protein
        self.carbs = carbs
        self.fat = fat
        self.quality = quality
        self.dataSource = dataSource
        self.confidence = confidence
    }
}

/// Food quality framing: whole / mixed / processed
/// NOT "good/bad" — avoids food moralizing
/// Based on NOVA classification research
enum FoodQuality: String {
    case whole = "Whole"          // Nutrient-dense, minimally processed
    case mixed = "Mixed"         // Some processing or mixed ingredients
    case processed = "Processed" // Ultra-processed (NOVA Group 4)

    var color: Color {
        switch self {
        case .whole: DSColor.Status.success
        case .mixed: DSColor.Status.warning
        case .processed: DSColor.Status.error
        }
    }
}

import SwiftUI

/// Where the nutrition data came from — transparency for the user
enum FoodDataSource: String {
    case usda = "USDA"             // Lab-analyzed, highest confidence
    case usdaBranded = "Label"    // Manufacturer-reported label data
    case openFoodFacts = "OFF"     // Crowdsourced, verified
    case fatSecret = "FatSecret"   // Commercial API
    case aiEstimate = "Estimated"  // Claude AI, flagged for user
    case userCorrected = "Custom"  // User manually adjusted values
}

// MARK: - Daily Nutrition Summary

struct DailyNutrition: Identifiable {
    let id = UUID()
    let date: Date
    var meals: [Meal]

    // Targets (from user profile / coach)
    var calorieTarget: Int = 2400
    var proteinTarget: Double = 150
    var carbTarget: Double = 250
    var fatTarget: Double = 65

    // Computed totals
    var totalCalories: Int { meals.reduce(0) { $0 + $1.totalCalories } }
    var totalProtein: Double { meals.reduce(0) { $0 + $1.totalProtein } }
    var totalCarbs: Double { meals.reduce(0) { $0 + $1.totalCarbs } }
    var totalFat: Double { meals.reduce(0) { $0 + $1.totalFat } }

    var caloriesRemaining: Int { calorieTarget - totalCalories }

    // Logging streak
    var streak: Int = 14

    /// Natural language calorie status (4th grade reading level)
    var calorieStatusText: String {
        let remaining = caloriesRemaining
        if remaining > 500 { return "Plenty of room left today" }
        if remaining > 200 { return "Room for a snack" }
        if remaining > 0 { return "Almost at your target" }
        return "Over your target today"
    }

    /// Overall food quality for the day
    var overallQuality: FoodQuality {
        let allItems = meals.flatMap(\.items)
        guard !allItems.isEmpty else { return .whole }
        let wholeCount = allItems.filter { $0.quality == .whole }.count
        let processedCount = allItems.filter { $0.quality == .processed }.count
        if wholeCount > allItems.count / 2 { return .whole }
        if processedCount > allItems.count / 2 { return .processed }
        return .mixed
    }

    var qualityText: String {
        switch overallQuality {
        case .whole: "Mostly whole foods today"
        case .mixed: "A mix of foods today"
        case .processed: "A bit heavy on processed stuff"
        }
    }
}
