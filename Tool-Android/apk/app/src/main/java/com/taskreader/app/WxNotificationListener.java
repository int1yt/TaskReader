package com.taskreader.app;

import android.app.Notification;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;
import android.util.Log;

import com.chaquo.python.Python;

import org.json.JSONObject;

import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 监听微信通知，仅对「自己」的消息触发任务分解与自动回复。
 *
 * 工作原理：
 *   用户打开微信「自己」聊天窗口 → 发送一条消息 →
 *   通知栏出现消息（sender=用户微信名）→ 本服务检测到 →
 *   过滤 sender 匹配配置的 self_name → 调用 AI 分解 →
 *   通过广播交给 WeChatBotService 在无障碍中输入并发送回复。
 *
 * 同时支持触发关键词：文本以配置的 trigger_keyword 开头时，
 * 无论 sender 是谁都会触发（方便测试）。
 */
public class WxNotificationListener extends NotificationListenerService {

    private static final String TAG = "WxNotif";
    private static final String WX = "com.tencent.mm";
    private final ExecutorService w = Executors.newSingleThreadExecutor();
    private final Set<String> seen = new HashSet<>();

    @Override
    public void onCreate() {
        super.onCreate();
        Log.i(TAG, "listener created");
    }

    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        if (!sbn.getPackageName().equals(WX)) return;

        SharedPreferences prefs = getSharedPreferences(WeChatBotService.PREF, MODE_PRIVATE);
        if (!prefs.getBoolean("on", true)) return;

        Notification n = sbn.getNotification();
        if (n == null) return;

        Bundle extras = n.extras;
        String sender = String.valueOf(extras.getCharSequence("android.title", ""));
        String text = String.valueOf(extras.getCharSequence("android.text", ""));
        if (text.isEmpty()) text = String.valueOf(extras.getCharSequence("android.summaryText", ""));
        if (text.isEmpty() && n.tickerText != null) text = n.tickerText.toString();

        if (sender.isEmpty() || text.isEmpty()) return;

        Log.i(TAG, "notif: [" + sender + "] " + text.substring(0, Math.min(30, text.length())));

        // 读取配置：self_name / trigger_keyword
        String selfName = prefs.getString("self_name", "");
        String triggerKw = prefs.getString("trigger_keyword", "/task");
        String selfNameLower = selfName.trim().toLowerCase();
        String senderLower = sender.trim().toLowerCase();

        boolean isSelf = !selfName.isEmpty() && senderLower.equals(selfNameLower);
        boolean hasTrigger = !triggerKw.isEmpty() && text.trim().startsWith(triggerKw);

        if (!isSelf && !hasTrigger) {
            Log.d(TAG, "skipped: sender=" + sender + ", self=" + selfName + ", kw=" + triggerKw);
            return;
        }

        // 去重（30字前缀 + 按 sender 区分的 key）
        final String cleanMsg = hasTrigger && !isSelf
                ? text.trim().substring(triggerKw.length()).trim()
                : text;
        if (cleanMsg.isEmpty()) return;
        String dedupKey = sender.hashCode() + ":" + cleanMsg.substring(0, Math.min(30, cleanMsg.length()));
        synchronized (seen) {
            if (seen.contains(dedupKey)) return;
            seen.add(dedupKey);
            if (seen.size() > 500) seen.clear();
        }

        w.submit(() -> {
            try {
                String reply = WeChatBotService.classifyOffline(WxNotificationListener.this, cleanMsg);
                if (reply != null) {
                    Intent intent = new Intent("com.taskreader.app.SEND_REPLY");
                    intent.putExtra("reply", reply);
                    intent.putExtra("sender", sender);
                    intent.putExtra("is_self", isSelf);
                    sendBroadcast(intent);
                    Log.i(TAG, "queued reply for: [" + sender + "] "
                            + reply.substring(0, Math.min(30, reply.length())));
                }
            } catch (Exception e) { Log.e(TAG, "classify err", e); }
        });
    }

    @Override
    public void onNotificationRemoved(StatusBarNotification sbn) {}
}
