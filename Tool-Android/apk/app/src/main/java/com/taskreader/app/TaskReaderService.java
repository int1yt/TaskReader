package com.taskreader.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;

import androidx.annotation.Nullable;

import com.chaquo.python.Python;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 前台服务：运行 Python 任务解析引擎，接收 Xposed hook 的解析请求并返回结果。
 *
 * 通信协议：
 *   Hook（微信进程） → 广播 ACTION_PARSE（content + msg_id）
 *   → TaskReaderService 解析 → 广播 ACTION_REPLY（reply + msg_id）→ Hook 接收
 */
public class TaskReaderService extends Service {

    private static final String TAG = "TaskReaderSvc";
    static final String ACTION_PARSE = "com.taskreader.app.PARSE_MESSAGE";
    static final String ACTION_REPLY = "com.taskreader.app.PARSE_REPLY";
    private static final String CHANNEL_ID = "taskreader_service";
    private static final int NOTIFY_ID = 1001;

    private final ExecutorService w = Executors.newSingleThreadExecutor();
    private BroadcastReceiver parseReceiver;
    private volatile boolean pyOk = false;

    @Override
    public void onCreate() {
        super.onCreate();
        createChannel();
        startForeground(NOTIFY_ID, buildNotification("等待微信消息..."));

        // 初始化 Python
        w.submit(() -> {
            try {
                Python py = Python.getInstance();
                py.getModule("jieba").callAttr("initialize");
                py.getModule("bot.core").callAttr("BotCore");
                pyOk = true;
                Log.i(TAG, "Python engine ready");
            } catch (Exception e) {
                Log.e(TAG, "Python init failed", e);
            }
        });

        // 注册解析请求接收器
        parseReceiver = new BroadcastReceiver() {
            @Override
            public void onReceive(Context context, Intent intent) {
                String content = intent.getStringExtra("content");
                long msgId = intent.getLongExtra("msg_id", 0);
                if (content == null || content.isEmpty()) return;
                Log.i(TAG, "Parse request: " + content.substring(0, Math.min(30, content.length())));

                w.submit(() -> {
                    try {
                        // 等待 Python 就绪
                        int retries = 0;
                        while (!pyOk && retries < 30) {
                            Thread.sleep(500);
                            retries++;
                        }
                        if (!pyOk) {
                            sendReply("引擎未就绪，请稍后重试", msgId);
                            return;
                        }

                        // 解析任务
                        updateNotification("正在分解任务...");
                        String result;
                        try {
                            result = Python.getInstance().getModule("bot.core")
                                    .callAttr("BotCore")
                                    .callAttr("handle_text_json", content, false).toString();
                        } catch (Exception e) {
                            sendReply("解析出错: " + e.getMessage(), msgId);
                            updateNotification("等待微信消息...");
                            return;
                        }

                        // 从 JSON 提取文本
                        String reply = extractText(result);
                        if (reply == null) {
                            reply = "没有识别到任务，换个说法试试？";
                        }

                        updateNotification("等待微信消息...");
                        sendReply(reply, msgId);
                        Log.i(TAG, "Reply sent: " + reply.substring(0, Math.min(30, reply.length())));

                    } catch (Exception e) {
                        Log.e(TAG, "Parse error", e);
                        sendReply("解析出错: " + e.getMessage(), msgId);
                        updateNotification("等待微信消息...");
                    }
                });
            }
        };
        registerReceiver(parseReceiver, new IntentFilter(ACTION_PARSE), 0);
    }

    private String extractText(String json) {
        try {
            int ti = json.indexOf("\"text\":\"");
            if (ti == -1) return null;
            ti += 8;
            int te = json.indexOf("\",\"tasks\"", ti);
            if (te == -1) te = json.indexOf("\",\"source\"", ti);
            if (te == -1) return null;
            return json.substring(ti, te).replace("\\n", "\n").replace("\\\"", "\"");
        } catch (Exception e) {
            return null;
        }
    }

    private void sendReply(String reply, long msgId) {
        Intent intent = new Intent(ACTION_REPLY);
        intent.putExtra("reply", reply);
        intent.putExtra("msg_id", msgId);
        sendBroadcast(intent);
    }

    private void updateNotification(String text) {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm != null) {
            nm.notify(NOTIFY_ID, buildNotification(text));
        }
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel ch = new NotificationChannel(
                    CHANNEL_ID, "TaskReader", NotificationManager.IMPORTANCE_LOW);
            ch.setDescription("任务解析引擎运行中");
            NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
            if (nm != null) nm.createNotificationChannel(ch);
        }
    }

    private Notification buildNotification(String text) {
        Intent intent = new Intent(this, MainActivity.class);
        PendingIntent pi = PendingIntent.getActivity(
                this, 0, intent, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        return new Notification.Builder(this, CHANNEL_ID)
                .setContentTitle("TaskReader")
                .setContentText(text)
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentIntent(pi)
                .setOngoing(true)
                .build();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        return START_STICKY;
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        try { unregisterReceiver(parseReceiver); } catch (Exception ignore) {}
        super.onDestroy();
    }
}
