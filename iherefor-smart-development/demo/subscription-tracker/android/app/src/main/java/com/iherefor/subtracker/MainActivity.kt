package com.iherefor.subtracker

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.iherefor.subtracker.domain.BillingCycle
import com.iherefor.subtracker.domain.Subscription
import com.iherefor.subtracker.domain.SubscriptionRules
import java.time.LocalDate

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                SubscriptionScreen()
            }
        }
    }
}

fun sampleSubscriptions(): List<Subscription> = listOf(
    Subscription("Netflix", 1999, BillingCycle.MONTHLY, LocalDate.parse("2026-09-01")),
    Subscription("Spotify", 500, BillingCycle.MONTHLY, LocalDate.parse("2026-09-01"), trialEndsAt = LocalDate.parse("2026-09-20")),
    Subscription("iCloud+", 12000, BillingCycle.YEARLY, LocalDate.parse("2026-03-01")),
    Subscription("健身年卡", 6000, BillingCycle.YEARLY, LocalDate.parse("2026-06-15"), canceledAt = LocalDate.parse("2026-09-01"))
)

@androidx.compose.runtime.Composable
fun SubscriptionScreen() {
    val subscriptions = remember { mutableStateListOf<Subscription>().apply { addAll(sampleSubscriptions()) } }
    var showAddDialog by remember { mutableStateOf(false) }

    val today = LocalDate.now()
    val summary = SubscriptionRules.summarize(subscriptions.toList(), today)

    Scaffold(
        topBar = {
            Text(
                text = "订阅",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Medium,
                modifier = Modifier.padding(16.dp)
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { showAddDialog = true }) {
                Text("+", style = MaterialTheme.typography.headlineSmall)
            }
        }
    ) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            Text(
                text = "每月总支出：¥${"%.2f".format(summary.monthlyTotalCents / 100.0)}  ·  共 ${subscriptions.size} 条",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.fillMaxWidth().padding(16.dp)
            )
            LazyColumn {
                items(subscriptions) { sub ->
                    val snap = SubscriptionRules.evaluate(sub, today)
                    Card(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp)) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(
                                    text = sub.name,
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Medium
                                )
                                Spacer(modifier = Modifier.weight(1f))
                                Text(text = "¥${"%.2f".format(snap.monthlyCents / 100.0)}")
                            }
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = "下次扣款：${snap.nextBillingDate}" + when (snap.status) {
                                    com.iherefor.subtracker.domain.SubscriptionStatus.TRIAL -> "  ·  试用中"
                                    com.iherefor.subtracker.domain.SubscriptionStatus.CANCELED -> "  ·  已取消"
                                    com.iherefor.subtracker.domain.SubscriptionStatus.EXPIRED -> "  ·  已过期"
                                    else -> ""
                                },
                                style = MaterialTheme.typography.bodyMedium
                            )
                        }
                    }
                }
            }
        }
    }

    if (showAddDialog) {
        AddSubscriptionDialog(
            onDismiss = { showAddDialog = false },
            onAdd = { name, cents ->
                subscriptions.add(Subscription(name, cents, BillingCycle.MONTHLY, today))
                showAddDialog = false
            }
        )
    }
}

@androidx.compose.runtime.Composable
fun AddSubscriptionDialog(onDismiss: () -> Unit, onAdd: (String, Int) -> Unit) {
    var name by remember { mutableStateOf("") }
    var cents by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("添加订阅") },
        text = {
            Column {
                OutlinedTextField(value = name, onValueChange = { name = it }, label = { Text("名称") })
                Spacer(modifier = Modifier.height(8.dp))
                OutlinedTextField(value = cents, onValueChange = { cents = it }, label = { Text("金额（分）") })
            }
        },
        confirmButton = {
            TextButton(onClick = {
                val c = cents.toIntOrNull() ?: 0
                if (name.isNotBlank() && c > 0) onAdd(name, c)
            }) { Text("添加") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } }
    )
}
