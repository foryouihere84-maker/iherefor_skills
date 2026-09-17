package com.iherefor.subtracker.domain

import java.time.LocalDate
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class SubscriptionRulesTest {

    private fun date(s: String) = LocalDate.parse(s)

    private fun sub(
        name: String = "Netflix",
        priceCents: Int = 1999,
        cycle: BillingCycle = BillingCycle.MONTHLY,
        startedAt: String = "2023-01-31",
        trialEndsAt: String? = null,
        canceledAt: String? = null
    ) = Subscription(name, priceCents, cycle, date(startedAt), trialEndsAt?.let(::date), canceledAt?.let(::date))

    // ---- 切片 1：dueDate ----
    @Test
    fun `dueDate monthly clamps to end of month`() {
        assertEquals(date("2023-02-28"), SubscriptionRules.dueDate(date("2023-01-31"), BillingCycle.MONTHLY, 1))
    }

    @Test
    fun `dueDate monthly leap year clamps`() {
        assertEquals(date("2024-02-29"), SubscriptionRules.dueDate(date("2024-01-31"), BillingCycle.MONTHLY, 1))
    }

    @Test
    fun `dueDate anchor single step does not drift`() {
        // 链式 1/31 +1M +1M = 3/28（漂移）；锚点单步 +2M 应 = 3/31
        assertEquals(date("2023-03-31"), SubscriptionRules.dueDate(date("2023-01-31"), BillingCycle.MONTHLY, 2))
    }

    @Test
    fun `dueDate yearly clamps leap day`() {
        assertEquals(date("2025-02-28"), SubscriptionRules.dueDate(date("2024-02-29"), BillingCycle.YEARLY, 1))
    }

    @Test
    fun `dueDate weekly advances`() {
        assertEquals(date("2023-01-09"), SubscriptionRules.dueDate(date("2023-01-02"), BillingCycle.WEEKLY, 1))
    }

    @Test
    fun `dueDate occurrence zero returns anchor`() {
        assertEquals(date("2023-01-31"), SubscriptionRules.dueDate(date("2023-01-31"), BillingCycle.MONTHLY, 0))
    }

    @Test
    fun `dueDate negative occurrence returns null`() {
        assertNull(SubscriptionRules.dueDate(date("2023-01-31"), BillingCycle.MONTHLY, -1))
    }

    // ---- 切片 2：evaluate ----
    @Test
    fun `evaluate trial status when trial not ended`() {
        val snap = SubscriptionRules.evaluate(sub(trialEndsAt = "2099-01-01"), date("2023-01-15"))
        assertEquals(SubscriptionStatus.TRIAL, snap.status)
    }

    @Test
    fun `evaluate active status after trial ended`() {
        val snap = SubscriptionRules.evaluate(sub(trialEndsAt = "2023-01-10"), date("2023-01-15"))
        assertEquals(SubscriptionStatus.ACTIVE, snap.status)
    }

    @Test
    fun `evaluate canceled overrides trial`() {
        val snap = SubscriptionRules.evaluate(sub(trialEndsAt = "2099-01-01", canceledAt = "2023-01-05"), date("2023-01-15"))
        assertEquals(SubscriptionStatus.CANCELED, snap.status)
    }

    @Test
    fun `evaluate next billing date strictly after asOf`() {
        val snap = SubscriptionRules.evaluate(sub(startedAt = "2023-01-31"), date("2023-02-10"))
        assertEquals(date("2023-02-28"), snap.nextBillingDate)
    }

    @Test
    fun `evaluate monthly cents for monthly cycle`() {
        val snap = SubscriptionRules.evaluate(sub(), date("2023-01-15"))
        assertEquals(1999, snap.monthlyCents)
    }

    @Test
    fun `evaluate trial days left`() {
        val snap = SubscriptionRules.evaluate(sub(trialEndsAt = "2023-01-20"), date("2023-01-15"))
        assertEquals(5, snap.trialDaysLeft)
    }

    // ---- 切片 3：summarize ----
    @Test
    fun `summarize monthly total`() {
        val a = sub(name = "Netflix", priceCents = 1999, startedAt = "2023-01-01")
        val b = sub(name = "Spotify", priceCents = 500, startedAt = "2023-01-01")
        val sum = SubscriptionRules.summarize(listOf(a, b), date("2023-01-15"))
        assertEquals(2499, sum.monthlyTotalCents)
    }

    @Test
    fun `summarize yearly divides by 12`() {
        val a = sub(name = "iCloud", priceCents = 12000, cycle = BillingCycle.YEARLY, startedAt = "2023-01-01")
        val sum = SubscriptionRules.summarize(listOf(a), date("2023-01-15"))
        assertEquals(1000, sum.monthlyTotalCents)
    }

    @Test
    fun `summarize trial ending soon filters trial within horizon`() {
        val a = sub(trialEndsAt = "2023-01-18", startedAt = "2023-01-01")
        val sum = SubscriptionRules.summarize(listOf(a), date("2023-01-15"))
        assertEquals(1, sum.trialEndingSoon.size)
    }

    @Test
    fun `summarize excludes canceled from total`() {
        val a = sub(startedAt = "2023-01-01", canceledAt = "2023-01-10")
        val sum = SubscriptionRules.summarize(listOf(a), date("2023-01-15"))
        assertEquals(0, sum.monthlyTotalCents)
    }

    @Test
    fun `summarize empty list is zero`() {
        val sum = SubscriptionRules.summarize(emptyList(), date("2023-01-15"))
        assertEquals(0, sum.monthlyTotalCents)
        assertEquals(0, sum.snapshots.size)
    }
}
