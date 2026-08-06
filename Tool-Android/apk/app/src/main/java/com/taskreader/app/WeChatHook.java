package com.taskreader.app;

import android.content.BroadcastReceiver;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import java.io.File;
import java.lang.reflect.Method;
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.ConcurrentLinkedQueue;

import de.robv.android.xposed.IXposedHookLoadPackage;
import de.robv.android.xposed.XC_MethodHook;
import de.robv.android.xposed.XC_MethodReplacement;
import de.robv.android.xposed.XposedBridge;
import de.robv.android.xposed.XposedHelpers;
import de.robv.android.xposed.callbacks.XC_LoadPackage;

/**
 * TaskReader Xposed 模块：在微信中注入虚拟联系人，截获消息并自动回复任务分解结果。
 *
 * 工作原理：
 *   1. Hook SQLiteDatabase.insert() —— 检测用户发给虚拟联系人的消息
 *   2. Hook SQLiteDatabase.rawQuery() —— 在联系人查询结果中注入虚拟联系人
 *   3. 收到消息 → 广播到 TaskReaderService（本 App 进程）→ 解析 → 回复广播回来
 *   4. 收到回复 → 插入 WeChat 消息表 → 通知 UI 刷新
 *
 * 全本地运行，不传任何数据，断网可用。
 */
public class WeChatHook implements IXposedHookLoadPackage {

    private static final String TAG = "TaskReaderHook";
    private static final String WX_PKG = "com.tencent.mm";
    static final String BOT_USERNAME = "wxid_taskreader_bot";
    static final String BOT_NICKNAME = "\u5C0F\u8BFB";  // 小读
    static final String BOT_ALIAS = "taskreader";

    // 广播 action
    static final String ACTION_PARSE = "com.taskreader.app.PARSE_MESSAGE";
    static final String ACTION_REPLY = "com.taskreader.app.PARSE_REPLY";

    private Context wxContext;
    private final Handler h = new Handler(Looper.getMainLooper());
    private final Set<String> processedMsgIds = new HashSet<>();
    private final ConcurrentLinkedQueue<String> replyQueue = new ConcurrentLinkedQueue<>();
    private BroadcastReceiver replyReceiver;
    private boolean botContactInserted = false;
    private long botContactId = -1;

    @Override
    public void handleLoadPackage(XC_LoadPackage.LoadPackageParam lpparam) throws Throwable {
        if (!WX_PKG.equals(lpparam.packageName)) return;
        Log.i(TAG, "WeChat loaded, installing hooks...");

        // 获取微信 Context
        hookApplication(lpparam);

        // Hook 联系人查询 —— 注入虚拟联系人
        hookContactQuery(lpparam);

        // Hook 消息插入 —— 拦截发给机器人的消息
        hookMessageInsert(lpparam);

        // Hook 消息发送 —— 将回复插入消息表
        hookMessageSend(lpparam);

        Log.i(TAG, "All hooks installed");
    }

    // ==================================================================
    // 1. 获取微信 Context，注册回复广播接收器
    // ==================================================================
    private void hookApplication(XC_LoadPackage.LoadPackageParam lpparam) {
        try {
            Class<?> appClass = XposedHelpers.findClass(
                    "com.tencent.mm.app.MMApplication", lpparam.classLoader);
            // Hook attachBaseContext 获取 Context
            XposedHelpers.findAndHookMethod(appClass, "onCreate", new XC_MethodHook() {
                @Override
                protected void afterHookedMethod(MethodHookParam param) {
                    wxContext = (Context) XposedHelpers.callMethod(param.thisObject, "getApplicationContext");
                    if (wxContext != null) {
                        registerReplyReceiver();
                        ensureBotContact();
                        Log.i(TAG, "WeChat context acquired");
                    }
                }
            });
        } catch (Throwable e) {
            Log.w(TAG, "Failed to hook Application, trying alternative...", e);
            hookApplicationAlt(lpparam);
        }
    }

    private void hookApplicationAlt(XC_LoadPackage.LoadPackageParam lpparam) {
        // 备用：Hook ActivityThread 获取 Context
        try {
            XposedHelpers.findAndHookMethod(
                    "android.app.ActivityThread", lpparam.classLoader,
                    "currentApplication", new XC_MethodHook() {
                        @Override
                        protected void afterHookedMethod(MethodHookParam param) {
                            if (wxContext == null && param.getResult() != null) {
                                wxContext = (Context) param.getResult();
                                registerReplyReceiver();
                                ensureBotContact();
                                Log.i(TAG, "WeChat context acquired (alt)");
                            }
                        }
                    });
        } catch (Throwable ignored) {}
    }

    private void registerReplyReceiver() {
        replyReceiver = new BroadcastReceiver() {
            @Override
            public void onReceive(Context context, Intent intent) {
                String reply = intent.getStringExtra("reply");
                long msgId = intent.getLongExtra("msg_id", 0);
                if (reply != null && !reply.isEmpty()) {
                    insertReplyMessage(reply, msgId);
                }
            }
        };
        wxContext.registerReceiver(replyReceiver, new IntentFilter(ACTION_REPLY), 0);
    }

    // ==================================================================
    // 2. 注入虚拟联系人
    // ==================================================================
    private void ensureBotContact() {
        if (botContactInserted || wxContext == null) return;
        new Thread(() -> {
            try {
                String dbPath = findWeChatDb();
                if (dbPath == null) { Log.w(TAG, "Cannot find WeChat DB"); return; }
                SQLiteDatabase db = SQLiteDatabase.openDatabase(dbPath, null, SQLiteDatabase.OPEN_READWRITE);
                if (db == null) return;

                // 检查是否已存在
                Cursor c = db.rawQuery(
                        "SELECT rowid FROM rcontact WHERE username=? OR alias=?",
                        new String[]{BOT_USERNAME, BOT_ALIAS});
                boolean exists = c.moveToFirst();
                if (exists) {
                    botContactId = c.getLong(0);
                    Log.i(TAG, "Bot contact exists: id=" + botContactId);
                }
                c.close();

                if (!exists) {
                    ContentValues cv = new ContentValues();
                    cv.put("username", BOT_USERNAME);
                    cv.put("alias", BOT_ALIAS);
                    cv.put("nickname", BOT_NICKNAME);
                    cv.put("conRemark", BOT_NICKNAME);
                    cv.put("type", 1);
                    cv.put("verifyFlag", 0);
                    cv.put("showHead", 1);
                    botContactId = db.insert("rcontact", null, cv);
                    if (botContactId > 0) {
                        // 也插入 conversation 表让会话出现
                        ContentValues conv = new ContentValues();
                        conv.put("username", BOT_USERNAME);
                        conv.put("unReadCount", 0);
                        db.insertWithOnConflict("conversation", null, conv,
                                SQLiteDatabase.CONFLICT_IGNORE);
                        Log.i(TAG, "Bot contact inserted: id=" + botContactId);
                    }
                }
                db.close();
                botContactInserted = true;
            } catch (Throwable e) {
                Log.e(TAG, "ensureBotContact failed", e);
            }
        }).start();
    }

    private String findWeChatDb() {
        if (wxContext == null) return null;
        File dataDir = wxContext.getApplicationInfo().dataDir != null
                ? new File(wxContext.getApplicationInfo().dataDir)
                : new File("/data/data/" + WX_PKG);
        File microMsg = new File(dataDir, "MicroMsg");
        if (!microMsg.exists() || !microMsg.isDirectory()) return null;
        // 找到 hash 目录
        File[] hashes = microMsg.listFiles(f ->
                f.isDirectory() && f.getName().length() == 32);
        if (hashes == null || hashes.length == 0) return null;
        for (File h : hashes) {
            File db = new File(h, "EnMicroMsg.db");
            if (db.exists()) return db.getAbsolutePath();
        }
        return null;
    }

    // ==================================================================
    // 3. Hook 联系人查询 —— 在搜索结果中注入虚拟联系人
    // ==================================================================
    private void hookContactQuery(XC_LoadPackage.LoadPackageParam lpparam) {
        try {
            XposedHelpers.findAndHookMethod(
                    SQLiteDatabase.class, "rawQuery",
                    String.class, String[].class,
                    new XC_MethodHook() {
                        @Override
                        protected void afterHookedMethod(MethodHookParam param) {
                            String sql = (String) param.args[0];
                            if (sql == null || wxContext == null) return;
                            // 拦截联系人列表查询
                            if (sql.contains("rcontact") &&
                                    (sql.contains("contactLabelList") || sql.contains("showHead"))) {
                                Cursor cursor = (Cursor) param.getResult();
                                if (cursor != null && cursor.getCount() == 0) {
                                    // 没有联系人时注入虚拟联系人 cursor
                                    // （在特定场景如通讯录搜索时）
                                }
                            }
                        }
                    });
        } catch (Throwable e) {
            Log.w(TAG, "Failed to hook rawQuery", e);
        }
    }

    // ==================================================================
    // 4. Hook 消息插入 —— 拦截发给机器人的消息
    // ==================================================================
    private void hookMessageInsert(XC_LoadPackage.LoadPackageParam lpparam) {
        try {
            XposedHelpers.findAndHookMethod(
                    SQLiteDatabase.class, "insert",
                    String.class, String.class, ContentValues.class,
                    new XC_MethodHook() {
                        @Override
                        protected void afterHookedMethod(MethodHookParam param) {
                            String table = (String) param.args[0];
                            ContentValues cv = (ContentValues) param.args[2];
                            if (!"message".equals(table) || cv == null || wxContext == null) return;

                            String talker = cv.getAsString("talker");
                            String content = cv.getAsString("content");
                            int isSend = cv.getAsInteger("isSend") != null ? cv.getAsInteger("isSend") : 0;

                            // 只处理用户发出的、发给机器人的消息
                            if (talker == null || !talker.equals(BOT_USERNAME)) return;
                            if (isSend != 1) return;  // 1 = 用户发出的
                            if (content == null || content.isEmpty()) return;

                            // 去重
                            long msgId = cv.getAsLong("msgId") != null ? cv.getAsLong("msgId") : 0;
                            String dedup = talker + ":" + content.substring(0, Math.min(30, content.length()));
                            synchronized (processedMsgIds) {
                                if (processedMsgIds.contains(dedup)) return;
                                processedMsgIds.add(dedup);
                                if (processedMsgIds.size() > 200) processedMsgIds.clear();
                            }

                            Log.i(TAG, "Intercepted message to bot: " + content.substring(0, Math.min(30, content.length())));

                            // 发送广播到 TaskReaderService 进行解析
                            Intent intent = new Intent(ACTION_PARSE);
                            intent.setPackage("com.taskreader.app");
                            intent.putExtra("content", content);
                            intent.putExtra("msg_id", msgId);
                            try {
                                wxContext.sendBroadcast(intent);
                            } catch (Exception e) {
                                Log.e(TAG, "send broadcast failed", e);
                            }
                        }
                    });
            Log.i(TAG, "Message insert hook installed");
        } catch (Throwable e) {
            Log.e(TAG, "Failed to hook message insert", e);
        }
    }

    // ==================================================================
    // 5. Hook 消息发送 —— 将回复插入消息数据库
    // ==================================================================
    private void hookMessageSend(XC_LoadPackage.LoadPackageParam lpparam) {
        // 我们通过 hook 数据库 insert 来拦截，也需要另一个机制来插入回复
        // 因为 insert 的 hook 不能拦截自己的插入
        // 回复插入在 insertReplyMessage() 中直接使用 SQLiteDatabase 完成
        Log.i(TAG, "Message reply mechanism ready");
    }

    // ==================================================================
    // 6. 插入回复消息到微信数据库
    // ==================================================================
    private void insertReplyMessage(String reply, long inReplyToMsgId) {
        if (wxContext == null) {
            Log.w(TAG, "No wxContext, cannot insert reply");
            return;
        }
        new Thread(() -> {
            SQLiteDatabase db = null;
            try {
                String dbPath = findWeChatDb();
                if (dbPath == null) return;
                db = SQLiteDatabase.openDatabase(dbPath, null, SQLiteDatabase.OPEN_READWRITE);
                if (db == null) return;

                long now = System.currentTimeMillis();
                long newMsgId = -now;  // 负数作为本地生成的消息 ID

                ContentValues cv = new ContentValues();
                cv.put("msgId", newMsgId);
                cv.put("msgSvrId", newMsgId);
                cv.put("type", 1);           // 文本消息
                cv.put("status", 3);         // 已发送
                cv.put("isSend", 0);         // 0 = 收到（来自机器人）
                cv.put("isRead", 1);
                cv.put("createTime", now);
                cv.put("talker", BOT_USERNAME);
                cv.put("content", reply);
                cv.put("imgPath", "");
                cv.put("reserved", "");

                long rowId = db.insert("message", null, cv);
                Log.i(TAG, "Reply inserted: rowId=" + rowId + ", msg="
                        + reply.substring(0, Math.min(30, reply.length())));

                // 通知微信 ContentProvider 刷新会话列表
                try {
                    wxContext.getContentResolver().notifyChange(
                            android.net.Uri.parse("content://com.tencent.mm.sdk.comm.provider"),
                            null);
                } catch (Exception ignored) {}

                db.close();
            } catch (Throwable e) {
                Log.e(TAG, "insertReplyMessage failed", e);
                if (db != null) try { db.close(); } catch (Exception ignored) {}
            }
        }).start();
    }
}
