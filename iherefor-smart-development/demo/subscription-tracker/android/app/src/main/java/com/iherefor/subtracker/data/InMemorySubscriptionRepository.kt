package com.iherefor.subtracker.data

import com.iherefor.subtracker.domain.Subscription

/**
 * Repository seam 的内存 adapter（对应 shared-layer.md 的 Repository 接口）。
 * 仅 all()；未来本地/云存储各写 adapter，领域层不动。
 */
class InMemorySubscriptionRepository(private val initial: List<Subscription> = emptyList()) {
    fun all(): List<Subscription> = initial
}
