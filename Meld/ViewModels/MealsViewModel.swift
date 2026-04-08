import Foundation

// MARK: - Meals View Model
// Manages daily meal data, logging, and streak tracking.
// Phase 1: mock data + text search logging.
// Phase 2: Claude Vision photo + barcode scanning.
// Phase 3: smart suggestions, saved meals, templates.

@Observable @MainActor
final class MealsViewModel {

    var dailyNutrition: DailyNutrition
    var searchText: String = ""
    var searchResults: [FoodItem] = []
    var isSearching: Bool = false
    var showInputSheet: Bool = false

    init() {
        self.dailyNutrition = Self.mockDay()
    }

    // MARK: - Actions

    func logMeal(_ meal: Meal) {
        dailyNutrition.meals.append(meal)
        DSHaptic.success()
    }

    func searchFood(_ query: String) {
        guard !query.isEmpty else {
            searchResults = []
            return
        }
        isSearching = true

        // Mock search results — will hit USDA + OFF databases in production
        Task {
            try? await Task.sleep(for: .seconds(0.5))
            searchResults = Self.mockSearchResults(for: query)
            isSearching = false
        }
    }

    func logFoodItem(_ item: FoodItem) {
        let meal = Meal(items: [item], source: .search)
        logMeal(meal)
        showInputSheet = false
        searchText = ""
        searchResults = []
    }

    // MARK: - Computed

    var recentMeals: [String] {
        ["Grilled chicken + rice", "Oatmeal + banana", "Protein shake", "Salad bowl"]
    }

    var timeBasedSuggestion: String? {
        let hour = Calendar.current.component(.hour, from: Date())
        switch hour {
        case 5..<11: return "My usual breakfast"
        case 11..<15: return "Same lunch as yesterday"
        case 17..<22: return "My usual dinner"
        default: return nil
        }
    }

    // MARK: - Mock Data

    private static func mockDay() -> DailyNutrition {
        DailyNutrition(
            date: Date(),
            meals: [
                Meal(
                    date: Calendar.current.date(bySettingHour: 7, minute: 30, second: 0, of: Date())!,
                    items: [
                        FoodItem(name: "Oatmeal", servingSize: "1 cup cooked", calories: 154, protein: 5, carbs: 27, fat: 3, quality: .whole, dataSource: .usda),
                        FoodItem(name: "Banana", servingSize: "1 medium", calories: 105, protein: 1, carbs: 27, fat: 0, quality: .whole, dataSource: .usda),
                        FoodItem(name: "Coffee with milk", servingSize: "12 oz", calories: 45, protein: 2, carbs: 4, fat: 2, quality: .whole, dataSource: .usda),
                    ]
                ),
                Meal(
                    date: Calendar.current.date(bySettingHour: 12, minute: 15, second: 0, of: Date())!,
                    items: [
                        FoodItem(name: "Grilled chicken breast", servingSize: "6 oz", calories: 280, protein: 53, carbs: 0, fat: 6, quality: .whole, dataSource: .usda),
                        FoodItem(name: "Brown rice", servingSize: "1 cup cooked", calories: 216, protein: 5, carbs: 45, fat: 2, quality: .whole, dataSource: .usda),
                        FoodItem(name: "Steamed broccoli", servingSize: "1 cup", calories: 55, protein: 4, carbs: 11, fat: 1, quality: .whole, dataSource: .usda),
                    ]
                ),
            ],
            calorieTarget: 2200,
            proteinTarget: 150,
            carbTarget: 220,
            fatTarget: 60,
            streak: 14
        )
    }

    private static func mockSearchResults(for query: String) -> [FoodItem] {
        let lowered = query.lowercased()
        let allFoods: [FoodItem] = [
            FoodItem(name: "Grilled Chicken Breast", servingSize: "6 oz", calories: 280, protein: 53, carbs: 0, fat: 6, quality: .whole, dataSource: .usda),
            FoodItem(name: "Chicken Thigh (skinless)", servingSize: "4 oz", calories: 210, protein: 26, carbs: 0, fat: 11, quality: .whole, dataSource: .usda),
            FoodItem(name: "Brown Rice", servingSize: "1 cup cooked", calories: 216, protein: 5, carbs: 45, fat: 2, quality: .whole, dataSource: .usda),
            FoodItem(name: "White Rice", servingSize: "1 cup cooked", calories: 206, protein: 4, carbs: 45, fat: 0, quality: .mixed, dataSource: .usda),
            FoodItem(name: "Banana", servingSize: "1 medium", calories: 105, protein: 1, carbs: 27, fat: 0, quality: .whole, dataSource: .usda),
            FoodItem(name: "Greek Yogurt (plain)", servingSize: "6 oz", calories: 100, protein: 17, carbs: 6, fat: 1, quality: .whole, dataSource: .usda),
            FoodItem(name: "Protein Shake (whey)", servingSize: "1 scoop + water", calories: 120, protein: 24, carbs: 3, fat: 1, quality: .mixed, dataSource: .openFoodFacts),
            FoodItem(name: "Oatmeal", servingSize: "1 cup cooked", calories: 154, protein: 5, carbs: 27, fat: 3, quality: .whole, dataSource: .usda),
            FoodItem(name: "Salmon Fillet", servingSize: "6 oz", calories: 350, protein: 34, carbs: 0, fat: 22, quality: .whole, dataSource: .usda),
            FoodItem(name: "Sweet Potato", servingSize: "1 medium", calories: 103, protein: 2, carbs: 24, fat: 0, quality: .whole, dataSource: .usda),
        ]
        return allFoods.filter { $0.name.lowercased().contains(lowered) }
    }
}
