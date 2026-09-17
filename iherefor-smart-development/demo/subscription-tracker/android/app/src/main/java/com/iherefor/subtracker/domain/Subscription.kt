package com.iherefor.subtracker.domain

import java.time.LocalDate

enum class BillingCycle { WEEKLY, MONTHLY, YEARLY }

enum class SubscriptionStatus { TRIAL, ACTIVE, EXPIRED, CANCELED }

data class Subscription(
    val name: String,
    val priceCents: Int,
    val cycle: BillingCycle,
    val startedAt: LocalDate,
    val trialEndsAt: LocalDate? = null,
    val canceledAt: LocalDate? = null
)

data class SubscriptionSnapshot(
    val status: SubscriptionStatus,
    val nextBillingDate: LocalDate,
    val monthlyCents: Int,
    val trialDaysLeft: Int
)

data class LedgerSummary(
    val monthlyTotalCents: Int,
    val snapshots: List<SubscriptionSnapshot>,
    val trialEndingSoon: List<SubscriptionSnapshot>
)

sealed class DomainError : Exception() {
    object InvalidPeriod : DomainError()
}
