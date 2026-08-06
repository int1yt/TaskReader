package com.taskreader.app;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

import com.chaquo.python.Python;

import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicBoolean;

public class MainActivity extends AppCompatActivity {

    private static final String MODEL_NAME = "qwen3_0_6b_mixed_int4.litertlm";

    private final Handler main = new Handler(Looper.getMainLooper());
    private LinearLayout loadingView;
    private TextView statusText, subText;
    private ProgressBar progressBar;
    private WebView webView;
    private volatile boolean ready = false;
    private volatile boolean llmReady = false;
    private String llmStatus = "";
    private final AtomicBoolean loading = new AtomicBoolean(false);

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        loadingView = new LinearLayout(this);
        loadingView.setOrientation(LinearLayout.VERTICAL);
        loadingView.setGravity(Gravity.CENTER);
        loadingView.setPadding(dp(48), dp(48), dp(48), dp(48));
        progressBar = new ProgressBar(this);
        progressBar.setIndeterminate(true);
        loadingView.addView(progressBar, new LinearLayout.LayoutParams(dp(200), dp(6)));
        statusText = new TextView(this);
        statusText.setText("正在启动…");
        statusText.setTextSize(16);
        statusText.setGravity(Gravity.CENTER);
        statusText.setPadding(0, dp(20), 0, 0);
        loadingView.addView(statusText);
        subText = new TextView(this);
        subText.setText("");
        subText.setTextSize(12);
        subText.setGravity(Gravity.CENTER);
        subText.setTextColor(0xFF999999);
        subText.setPadding(0, dp(8), 0, 0);
        loadingView.addView(subText);
        setContentView(loadingView);
        startInit();
    }

    private int dp(int v) { return (int)(v * getResources().getDisplayMetrics().density + 0.5f); }

    private void startInit() {
        if (loading.get()) return;
        loading.set(true);
        new Thread(() -> {
            try {
                setStatus("正在初始化引擎…", "");
                Python py = Python.getInstance();
                py.getModule("jieba").callAttr("initialize");

                setStatus("正在加载 AI 模型…", "");
                File dir = new File(getFilesDir(), "models");
                dir.mkdirs();
                File model = new File(dir, MODEL_NAME);

                if (!model.exists() || model.length() < 1024 * 1024) {
                    setStatus("首次使用：解压 AI 模型", "约 474MB，仅此一次");
                    try {
                        InputStream in = getAssets().open("models/" + MODEL_NAME);
                        FileOutputStream out = new FileOutputStream(model);
                        byte[] buf = new byte[65536];
                        long done = 0, total = in.available();
                        int n;
                        while ((n = in.read(buf)) > 0) {
                            out.write(buf, 0, n);
                            done += n;
                            final long d = done, t = total;
                            main.post(() -> setStatus("解压模型中… " + (t > 0 ? (int)(d * 100 / t) + "%" : ""),
                                    String.format(Locale.US, "%.0f / %.0f MB", d / 1048576.0, t / 1048576.0)));
                        }
                        out.close(); in.close();
                    } catch (Exception e) {
                        android.util.Log.w("TaskReader", "Model copy failed", e);
                    }
                }

                if (model.exists() && model.length() > 1024 * 1024 && !LlmEngine.isInitialized()) {
                    setStatus("加载 AI 模型到内存…", String.format(Locale.US, "%.0fMB", model.length() / 1048576.0));
                    LlmEngine.initialize(model.getAbsolutePath(), getCacheDir().getAbsolutePath());
                }
                llmReady = LlmEngine.isInitialized();
                llmStatus = llmReady ? "本地AI已就绪" : (model.exists() ? "加载失败，使用规则模式" : "模型未打包，使用规则模式");

                py.getModule("bot.core").callAttr("BotCore");
                ready = true;

                // 启动任务解析前台服务（供 Xposed hook 调用）
                main.post(() -> {
                    Intent svc = new Intent(MainActivity.this, TaskReaderService.class);
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                        startForegroundService(svc);
                    } else {
                        startService(svc);
                    }
                });

                main.post(() -> {
                    progressBar.setVisibility(View.GONE);
                    setStatus(llmReady ? "全部就绪" : "已就绪（规则模式）", llmStatus);
                    main.postDelayed(this::enterUi, 400);
                });
            } catch (Exception e) {
                android.util.Log.e("TaskReader", "init failed", e);
                ready = true;
                main.post(() -> { progressBar.setVisibility(View.GONE); setStatus("初始化失败", e.getMessage()); main.postDelayed(this::enterUi, 1500); });
            } finally { loading.set(false); }
        }).start();
    }

    private void setStatus(String s, String sub) { main.post(() -> { statusText.setText(s); subText.setText(sub); }); }

    @SuppressLint("SetJavaScriptEnabled")
    private void enterUi() {
        webView = new WebView(this);
        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true); s.setAllowFileAccess(true); s.setDomStorageEnabled(true);
        webView.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) { return false; }
        });
        webView.addJavascriptInterface(new Bridge(), "Bridge");
        setContentView(webView);
        webView.loadUrl("file:///android_asset/index.html");
    }

    private static final int REQ_PICK_AVATAR = 1001;
    private String pendingAvatarPath = null;

    @Override
    protected void onActivityResult(int requestCode, int resultCode, @Nullable Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQ_PICK_AVATAR && resultCode == Activity.RESULT_OK && data != null && data.getData() != null) {
            Uri uri = data.getData();
            try {
                File dir = new File(getFilesDir(), "avatars");
                dir.mkdirs();
                File dest = new File(dir, "avatar_" + System.currentTimeMillis() + ".png");
                InputStream in = getContentResolver().openInputStream(uri);
                FileOutputStream out = new FileOutputStream(dest);
                byte[] buf = new byte[8192];
                int n;
                while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
                in.close(); out.close();
                pendingAvatarPath = dest.getAbsolutePath();
                // 写入 Python config
                try {
                    String cfg = Python.getInstance().getModule("bot_config").callAttr("load_json").toString();
                    JSONObject o = new JSONObject(cfg);
                    o.getJSONObject("bot_profile").put("avatar_path", pendingAvatarPath);
                    Python.getInstance().getModule("bot_config").callAttr("save_json", o.toString());
                } catch (Exception ignore) {}
            } catch (Exception e) {
                android.util.Log.e("TaskReader", "avatar save failed", e);
            }
        }
    }

    private class Bridge {
        @JavascriptInterface public String parse(String sentence, boolean useLlm) {
            if (!ready) return "{\"ok\":false,\"error\":\"引擎未就绪\"}";
            try { return Python.getInstance().getModule("bot.core").callAttr("BotCore").callAttr("handle_text_json", sentence, useLlm && llmReady).toString(); }
            catch (Exception e) { return "{\"ok\":false,\"error\":\"" + e.getMessage() + "\"}"; }
        }
        @JavascriptInterface public boolean isLlmReady() { return llmReady; }
        @JavascriptInterface public String getLlmStatus() { return llmStatus; }
        @JavascriptInterface public String getConfig() {
            try { return Python.getInstance().getModule("bot_config").callAttr("load_json").toString(); } catch (Exception e) { return "{}"; }
        }
        @JavascriptInterface public boolean saveConfig(String json) {
            try {
                boolean ok = Python.getInstance().getModule("bot_config").callAttr("save_json", json).toBoolean();
                if (ok) {
                    // 同步 self_name / trigger_keyword 到 SharedPreferences
                    JSONObject o = new JSONObject(json);
                    JSONObject sys = o.optJSONObject("system");
                    if (sys != null) {
                        SharedPreferences.Editor e = getSharedPreferences(WeChatBotService.PREF, MODE_PRIVATE).edit();
                        String sn = sys.optString("wechat_self_name", "");
                        String tk = sys.optString("trigger_keyword", "/task");
                        if (!sn.isEmpty()) e.putString("self_name", sn);
                        if (!tk.isEmpty()) e.putString("trigger_keyword", tk);
                        e.apply();
                    }
                }
                return ok;
            } catch (Exception e) { return false; }
        }
        @JavascriptInterface public String getAvatarPath() {
            try {
                String cfg = Python.getInstance().getModule("bot_config").callAttr("load_json").toString();
                JSONObject o = new JSONObject(cfg);
                return o.getJSONObject("bot_profile").optString("avatar_path", "");
            } catch (Exception e) { return ""; }
        }
        @JavascriptInterface public void pickAvatar() {
            main.post(() -> {
                Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType("image/*");
                startActivityForResult(i, REQ_PICK_AVATAR);
            });
        }
        @JavascriptInterface public String getAvatarPathNow() {
            return pendingAvatarPath != null ? pendingAvatarPath : "";
        }
        @JavascriptInterface public String serverStart() {
            try { return Python.getInstance().getModule("wechat_server").callAttr("start_server", "0.0.0.0", 8080, "taskreader").toString(); }
            catch (Exception e) { return "{\"ok\":false,\"msg\":\"" + e.getMessage() + "\"}"; }
        }
        @JavascriptInterface public String serverStop() {
            try { return Python.getInstance().getModule("wechat_server").callAttr("stop_server").toString(); }
            catch (Exception e) { return "{\"ok\":false}"; }
        }
        @JavascriptInterface public String serverStatus() {
            try { return Python.getInstance().getModule("wechat_server").callAttr("server_status").toString(); }
            catch (Exception e) { return "{\"ok\":false,\"running\":false}"; }
        }
        @JavascriptInterface public boolean isAccessibilityOn() {
            String srv = getPackageName() + "/" + WeChatBotService.class.getName();
            String val = android.provider.Settings.Secure.getString(getContentResolver(),
                    android.provider.Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES);
            return val != null && val.contains(srv);
        }
        @JavascriptInterface public void openAccessibility() {
            main.post(() -> { try { startActivity(new Intent(android.provider.Settings.ACTION_ACCESSIBILITY_SETTINGS)); } catch (Exception e) {} });
        }
        @JavascriptInterface public boolean isNotificationOn() {
            String flat = android.provider.Settings.Secure.getString(getContentResolver(), "enabled_notification_listeners");
            return flat != null && flat.contains(getPackageName());
        }
        @JavascriptInterface public void openNotificationSettings() {
            main.post(() -> { try { startActivity(new Intent(android.provider.Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)); } catch (Exception e) {} });
        }
        @JavascriptInterface public boolean isBotRunning() { return WeChatBotService.isRunning(MainActivity.this); }
        @JavascriptInterface public void setBotRunning(boolean on) { WeChatBotService.setRunning(MainActivity.this, on); }
        @JavascriptInterface public boolean isXposedActive() {
            return false;  // Xposed 无法从模块自身检测，需在 LSPosed Manager 查看
        }
        @JavascriptInterface public boolean isTaskReaderServiceRunning() {
            android.app.ActivityManager am = (android.app.ActivityManager) getSystemService(ACTIVITY_SERVICE);
            if (am != null) {
                for (android.app.ActivityManager.RunningServiceInfo s : am.getRunningServices(100)) {
                    if (TaskReaderService.class.getName().equals(s.service.getClassName())) return true;
                }
            }
            return false;
        }
        @JavascriptInterface public void startTaskReaderService() {
            main.post(() -> {
                Intent svc = new Intent(MainActivity.this, TaskReaderService.class);
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    startForegroundService(svc);
                } else {
                    startService(svc);
                }
            });
        }
    }

    @Override public void onBackPressed() { if (webView != null && webView.canGoBack()) webView.goBack(); else super.onBackPressed(); }
}
