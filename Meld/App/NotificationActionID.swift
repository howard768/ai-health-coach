import Foundation

/// `UNNotificationAction.identifier` values used by the AppDelegate when
/// registering categories AND when matching `response.actionIdentifier`.
///
/// Pre-PR-H these were string literals (`"REVIEW"`, `"ASK_COACH"`, ...) at
/// both the registration site and the response-matching switch. The
/// registration site and the matching site MUST agree; a typo on either side
/// produced a silent no-match (notification action button did nothing) with
/// no compiler help. The 2026-04-15 maestro flakes that traced to a renamed
/// enum case (see feedback_test_fixture_audit_on_rename.md) are the same
/// failure mode. One enum keeps both ends in lockstep.
enum NotificationActionID: String, CaseIterable {
    case review = "REVIEW"
    case askCoach = "ASK_COACH"
    case tellMeMore = "TELL_ME_MORE"
    case windDown = "WIND_DOWN"
    case logNow = "LOG_NOW"
    case seeReview = "SEE_REVIEW"
}
