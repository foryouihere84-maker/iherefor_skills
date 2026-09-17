package com.iherefor.subtracker.domain

import java.time.LocalDate
import java.time.temporal.ChronoUnit

/**
 * 领域层纯函数（共享层语义见 shared-layer.md）：无状态、无 I/O、不读系统时钟。
 * 两端（iOS ObjC / Android Kotlin）语义严格对齐本实现。
 */
object SubscriptionRules {

    /**
     * 从锚点单步递推 occurrence 期的日期。occurrence=0 返回 anchor 本身。
     * 锚点单步（非链式累加）以规避月末漂移（1/31 +1M +1M = 3/28）。
     * occurrence < 0 返回 null。
     */
    fun dueDate(anchor: LocalDate, cycle: BillingCycle, occurrence: Int): LocalDate? {
        if (occurrence < 0) return null
        return when (cycle) {
            BillingCycle.WEEKLY -> anchor.plusWeeks(occurrence.toLong())
            BillingCycle.MONTHLY -> anchor.plusMonths(occurrence.toLong())
            BillingCycle.YEARLY -> anchor.plusYears(occurrence.toLong())
        }
    }

    private fun monthlyCents(priceCents: Int, cycle: BillingCycle): Int {
        return when (cycle) {
            BillingCycle.WEEKLY -> Math.round(priceCents * 52.0 / 12.0).toInt()
            BillingCycle.MONTHLY -> priceCents
            BillingCycle.YEARLY -> Math.round(priceCents / 12.0).toInt()
        }
    }

    fun evaluate(subscription: Subscription, asOf: LocalDate): SubscriptionSnapshot {
        // 1. nextBillingDate：找第一个严格晚于 asOf 的期次（每次仍从锚点单步算，不漂移）
        var nextBillingDate = subscription.startedAt
        var occurrence = 1
        while (occurrence <= 1200) {
            val candidate = dueDate(subscription.startedAt, subscription.cycle, occurrence)!!
            if (candidate.isAfter(asOf)) {
                nextBillingDate = candidate
                break
            }
            occurrence++
        }

        // 2. 状态判定：canceled > trial > (expired / active)
        val status: SubscriptionStatus = when {
            subscription.canceledAt != null -> SubscriptionStatus.CANCELED
            subscription.trialEndsAt != null && !asOf.isAfter(subscription.trialEndsAt) -> SubscriptionStatus.TRIAL
            else -> SubscriptionStatus.ACTIVE
        }

        // 3. 折月金额
        val monthly = monthlyCents(subscription.priceCents, subscription.cycle)

        // 4. 试用剩余天数（无试用 = -1）
        val trialDaysLeft: Int = subscription.trialEndsAt
            ?.let { ChronoUnit.DAYS.between(asOf, it).toInt() }
            ?: -1

        return SubscriptionSnapshot(status, nextBillingDate, monthly, trialDaysLeft)
    }

    fun summarize(
        subscriptions: List<Subscription>,
        asOf: LocalDate,
        trialHorizonDays: Int = 7
    ): LedgerSummary {
        val snapshots = subscriptions.map { evaluate(it, asOf) }
        val total = snapshots
            .filter { it.status == SubscriptionStatus.ACTIVE || it.status == SubscriptionStatus.TRIAL }
            .sumOf { it.monthlyCents }
        val trialEndingSoon = snapshots
            .filter { it.status == SubscriptionStatus.TRIAL && it.trialDaysLeft in 0..trialHorizonDays }
            .sortedBy { it.trialDaysLeft }
        val sorted = snapshots.sortedBy { it.nextBillingDate }

        return LedgerSummary(total, sorted, trialEndingSoon)
    }
}
