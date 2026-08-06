package com.taskreader.app;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.AccessibilityServiceInfo;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;

import com.chaquo.python.Python;

import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 通过无障碍服务在微信中输入并发送回复。
 * 消息检测由 WxNotificationListener 完成，本服务只负责发送。
 *
 * 收到广播后，先检查当前是否在正确的会话窗口（自聊窗口），
 * 不在则尝试导航；然后在输入框填入文本并点击发送。
 */
public class WeChatBotService extends AccessibilityService {

    private static final String TAG = "WxBotSend";
    static final String PREF = "wxbot_prefs";
    private static final String WX = "com.tencent.mm";

    private final Handler h = new Handler(Looper.getMainLooper());
    private final ExecutorService w = Executors.newSingleThreadExecutor();
    private final ConcurrentLinkedQueue<ReplyTask> replyQueue = new ConcurrentLinkedQueue<>();
    private volatile boolean pyOk = false;

    private static class ReplyTask {
        final String text;
        final String sender;
        ReplyTask(String text, String sender) { this.text = text; this.sender = sender; }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        registerReceiver(replyReceiver, new IntentFilter("com.taskreader.app.SEND_REPLY"), 0);
        Log.i(TAG, "send service created");
        ensurePy();
    }

    private final BroadcastReceiver replyReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            String reply = intent.getStringExtra("reply");
            String sender = intent.getStringExtra("sender");
            if (reply != null) replyQueue.offer(new ReplyTask(reply, sender != null ? sender : ""));
        }
    };

    @Override
    public void onDestroy() {
        try { unregisterReceiver(replyReceiver); } catch (Exception ignore) {}
        super.onDestroy();
    }

    @Override
    public void onServiceConnected() {
        super.onServiceConnected();
        AccessibilityServiceInfo i = new AccessibilityServiceInfo();
        i.eventTypes = AccessibilityEvent.TYPES_ALL_MASK;
        i.feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC;
        i.flags = AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS
                | AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS
                | AccessibilityServiceInfo.FLAG_REQUEST_TOUCH_EXPLORATION_MODE;
        i.packageNames = new String[]{WX};
        setServiceInfo(i);
        Log.i(TAG, "send service connected");
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        ReplyTask task = replyQueue.poll();
        if (task == null) return;
        // 事件类型为窗口变化或内容变化时才尝试发送
        int t = event.getEventType();
        if (t != AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED
                && t != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) return;
        h.postDelayed(() -> typeAndSend(task.text, task.sender), 500);
    }

    private void typeAndSend(String reply, String sender) {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) { Log.w(TAG, "no window"); return; }
        try {
            // 验证当前窗口是否为自聊窗口（标题匹配 sender 或包含"自己/我的"）
            if (!sender.isEmpty() && !isSelfChatWindow(root, sender)) {
                Log.w(TAG, "not in self-chat window, navigating...");
                if (!navigateToSelfChat(root, sender)) {
                    Log.w(TAG, "navigation failed, trying to send anyway...");
                }
                sleep(800);
                root = getRootInActiveWindow();
                if (root == null) return;
            }

            AccessibilityNodeInfo edit = findEdit(root);
            if (edit == null) { Log.w(TAG, "no EditText"); return; }
            Bundle a = new Bundle();
            a.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, reply);
            edit.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, a);
            sleep(200);

            root = getRootInActiveWindow();
            if (root == null) return;
            AccessibilityNodeInfo send = findSend(root);
            if (send == null) { Log.w(TAG, "no send btn"); return; }
            send.performAction(AccessibilityNodeInfo.ACTION_CLICK);
            Log.i(TAG, "sent: " + reply.substring(0, Math.min(30, reply.length())));
        } finally {
            try { if (root != null) root.recycle(); } catch (Exception ignore) {}
        }
    }

    /**
     * 检查当前窗口是否为目标自聊窗口。
     * 微信自聊窗口标题通常是用户昵称（和 sender 一致），
     * 也可能显示"自己"。
     */
    private boolean isSelfChatWindow(AccessibilityNodeInfo root, String sender) {
        String title = findWindowTitle(root);
        if (title.isEmpty()) return true;  // 无法判断时允许发送
        String t = title.toLowerCase();
        String s = sender.toLowerCase();
        return t.contains(s) || t.contains("自己") || t.contains("我的");
    }

    /**
     * 尝试通过返回键退出当前会话回到聊天列表，
     * 然后查找并点击目标会话。
     */
    private boolean navigateToSelfChat(AccessibilityNodeInfo root, String sender) {
        try {
            // 按返回键回到聊天列表
            performGlobalAction(GLOBAL_ACTION_BACK);
            sleep(600);
            root = getRootInActiveWindow();
            if (root == null) return false;

            // 在聊天列表中查找目标会话
            AccessibilityNodeInfo target = findChatItem(root, sender);
            if (target != null) {
                target.performAction(AccessibilityNodeInfo.ACTION_CLICK);
                sleep(600);
                Log.i(TAG, "navigated to chat: " + sender);
                return true;
            }
            // 备用：搜索框
            AccessibilityNodeInfo search = findSearchBox(root);
            if (search != null) {
                search.performAction(AccessibilityNodeInfo.ACTION_CLICK);
                sleep(300);
                Bundle a = new Bundle();
                a.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, sender);
                search.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, a);
                sleep(1200);
                root = getRootInActiveWindow();
                if (root != null) {
                    AccessibilityNodeInfo result = findFirstClickableText(root, sender);
                    if (result != null) {
                        result.performAction(AccessibilityNodeInfo.ACTION_CLICK);
                        sleep(600);
                        Log.i(TAG, "navigated via search: " + sender);
                        return true;
                    }
                }
            }
            return false;
        } catch (Exception e) {
            Log.e(TAG, "navigate error", e);
            return false;
        }
    }

    private String findWindowTitle(AccessibilityNodeInfo n) {
        if (n == null) return "";
        if (n.getClassName() != null && n.getClassName().toString().contains("TextView")
                && n.getText() != null && n.getText().length() > 0) {
            return n.getText().toString();
        }
        for (int i = 0; i < n.getChildCount(); i++) {
            String r = findWindowTitle(n.getChild(i));
            if (!r.isEmpty()) return r;
        }
        return "";
    }

    private AccessibilityNodeInfo findChatItem(AccessibilityNodeInfo n, String name) {
        if (n == null || name.isEmpty()) return null;
        if (n.getText() != null && n.getText().toString().contains(name) && n.isClickable()) {
            return n;
        }
        for (int i = 0; i < n.getChildCount(); i++) {
            AccessibilityNodeInfo r = findChatItem(n.getChild(i), name);
            if (r != null) return r;
        }
        return null;
    }

    private AccessibilityNodeInfo findSearchBox(AccessibilityNodeInfo n) {
        if (n == null) return null;
        if (n.getClassName() != null && n.getClassName().toString().contains("EditText")
                && n.isClickable()) return n;
        for (int i = 0; i < n.getChildCount(); i++) {
            AccessibilityNodeInfo r = findSearchBox(n.getChild(i));
            if (r != null) return r;
        }
        return null;
    }

    private AccessibilityNodeInfo findFirstClickableText(AccessibilityNodeInfo n, String name) {
        if (n == null) return null;
        if (n.getText() != null && n.getText().toString().contains(name) && n.isClickable()) return n;
        for (int i = 0; i < n.getChildCount(); i++) {
            AccessibilityNodeInfo r = findFirstClickableText(n.getChild(i), name);
            if (r != null) return r;
        }
        return null;
    }

    public void enqueueReply(String reply, String sender) {
        replyQueue.offer(new ReplyTask(reply, sender != null ? sender : ""));
    }

    private AccessibilityNodeInfo findEdit(AccessibilityNodeInfo n) {
        if (n == null) return null;
        if (n.getClassName() != null && n.getClassName().toString().contains("EditText")) return n;
        for (int i = 0; i < n.getChildCount(); i++) {
            AccessibilityNodeInfo r = findEdit(n.getChild(i));
            if (r != null) return r;
        }
        return null;
    }

    private AccessibilityNodeInfo findSend(AccessibilityNodeInfo n) {
        if (n == null) return null;
        if (n.isClickable()) {
            CharSequence d = n.getContentDescription();
            CharSequence t = n.getText();
            if ((d != null && (d.toString().contains("发送") || d.toString().contains("Send")))
                    || (t != null && (t.toString().contains("发送") || t.toString().contains("Send"))))
                return n;
        }
        for (int i = 0; i < n.getChildCount(); i++) {
            AccessibilityNodeInfo r = findSend(n.getChild(i));
            if (r != null) return r;
        }
        return null;
    }

    public static String classifyOffline(Context ctx, String text) {
        try {
            ensurePyStatic(ctx);
            String json = Python.getInstance().getModule("bot.core").callAttr("BotCore")
                    .callAttr("handle_text_json", text, false).toString();
            int ti = json.indexOf("\"text\":\"");
            if (ti == -1) return null;
            ti += 8;
            int te = json.indexOf("\",\"tasks\"", ti);
            if (te == -1) te = json.indexOf("\",\"source\"", ti);
            if (te == -1) return null;
            String body = json.substring(ti, te).replace("\\n", "\n").replace("\\\"", "\"");
            try {
                String cfg = Python.getInstance().getModule("bot_config").callAttr("load_json").toString();
                int ni = cfg.indexOf("\"name\":\"");
                if (ni != -1) { ni += 8; int ne = cfg.indexOf("\"", ni); if (ne != -1) body = "【" + cfg.substring(ni, ne) + "】\n" + body; }
            } catch (Exception ignore) {}
            return body;
        } catch (Exception e) { return null; }
    }

    private void ensurePy() {
        if (pyOk) return;
        try {
            Python py = Python.getInstance();
            py.getModule("bot.core").callAttr("BotCore");
            py.getModule("jieba").callAttr("initialize");
            pyOk = true;
            Log.i(TAG, "py ready");
        } catch (Exception e) { Log.e(TAG, "py err", e); h.postDelayed(this::ensurePy, 5000); }
    }

    private static volatile boolean pyStaticOk = false;
    private static void ensurePyStatic(Context ctx) {
        if (pyStaticOk) return;
        try {
            Python.getInstance().getModule("bot.core").callAttr("BotCore");
            Python.getInstance().getModule("jieba").callAttr("initialize");
            pyStaticOk = true;
        } catch (Exception e) { Log.e(TAG, "py static err", e); }
    }

    public static boolean isRunning(Context ctx) { return ctx.getSharedPreferences(PREF, MODE_PRIVATE).getBoolean("on", true); }
    public static void setRunning(Context ctx, boolean v) { ctx.getSharedPreferences(PREF, MODE_PRIVATE).edit().putBoolean("on", v).apply(); }

    private static void sleep(long ms) { try { Thread.sleep(ms); } catch (InterruptedException ignore) {} }
    @Override public void onInterrupt() {}
    @Override public int onStartCommand(Intent intent, int flags, int startId) { return START_STICKY; }
}
