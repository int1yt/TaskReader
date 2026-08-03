package com.taskreader.app;

import android.annotation.SuppressLint;
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
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;

import java.util.concurrent.atomic.AtomicBoolean;

/**
 * 任务提取助手 · 主界面
 *
 * 启动流程：先显示加载屏，在后台线程完成
 *   Python 启动 → jieba 分词预热 → LLM 模型实际加载进内存，
 * 全部就绪后才进入聊天界面。LLM 不可用时显示安装指引（不降级为纯规则）。
 */
public class MainActivity extends AppCompatActivity {

    private final Handler main = new Handler(Looper.getMainLooper());

    private LinearLayout loadingView;
    private TextView statusText;
    private ProgressBar progressBar;
    private Button retryButton;
    private LinearLayout failView;
    private TextView failText;

    private WebView webView;
    private volatile boolean pythonReady = false;
    private volatile boolean llmReady = false;
    private final AtomicBoolean loading = new AtomicBoolean(false);

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        buildLoadingView();
        setContentView(loadingView);
        startLoading();
    }

    // ---------- 加载屏 UI ----------
    private void buildLoadingView() {
        loadingView = new LinearLayout(this);
        loadingView.setOrientation(LinearLayout.VERTICAL);
        loadingView.setGravity(Gravity.CENTER);
        loadingView.setPadding(dp(48), dp(48), dp(48), dp(48));

        progressBar = new ProgressBar(this);
        LinearLayout.LayoutParams pp = new LinearLayout.LayoutParams(dp(56), dp(56));
        pp.gravity = Gravity.CENTER_HORIZONTAL;
        loadingView.addView(progressBar, pp);

        statusText = new TextView(this);
        statusText.setText("正在加载，请稍候…");
        statusText.setTextSize(15);
        statusText.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams tp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        tp.topMargin = dp(20);
        loadingView.addView(statusText, tp);

        failView = new LinearLayout(this);
        failView.setOrientation(LinearLayout.VERTICAL);
        failView.setGravity(Gravity.CENTER);
        failView.setVisibility(View.GONE);
        LinearLayout.LayoutParams fp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        fp.topMargin = dp(24);
        failView.setLayoutParams(fp);

        failText = new TextView(this);
        failText.setTextSize(13);
        failText.setGravity(Gravity.LEFT);
        failText.setLineSpacing(dp(4), 1f);
        failView.addView(failText, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        retryButton = new Button(this);
        retryButton.setText("重新加载");
        LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        bp.topMargin = dp(20);
        bp.gravity = Gravity.CENTER_HORIZONTAL;
        retryButton.setLayoutParams(bp);
        retryButton.setOnClickListener(v -> startLoading());
        failView.addView(retryButton);

        loadingView.addView(failView);
    }

    private int dp(int v) {
        return (int) (v * getResources().getDisplayMetrics().density + 0.5f);
    }

    private void setStatus(String text) {
        main.post(() -> statusText.setText(text));
    }

    private void showFail(String text) {
        main.post(() -> {
            progressBar.setVisibility(View.GONE);
            failView.setVisibility(View.VISIBLE);
            failText.setText(text);
            statusText.setText("初始化未完成");
        });
    }

    // ---------- 后台加载 ----------
    private void startLoading() {
        if (loading.get()) return;
        loading.set(true);
        pythonReady = false;
        llmReady = false;
        main.post(() -> {
            progressBar.setVisibility(View.VISIBLE);
            failView.setVisibility(View.GONE);
        });

        new Thread(() -> {
            try {
                // 1. Python 引擎（PyApplication 已启动解释器）
                setStatus("正在启动 Python 引擎…");
                Python py = Python.getInstance();

                // 2. 加载核心 + 预热 jieba 分词（首次构建词典较慢）
                setStatus("正在加载分词与解析引擎…");
                py.getModule("bot.core").callAttr("BotCore");
                py.getModule("jieba").callAttr("initialize");

                // 3. 连接本地 Ollama 并检查模型
                setStatus("正在连接本地 AI 模型…");
                PyObject client = py.getModule("task_reader.llm").callAttr("OllamaClient");
                boolean ok = client.callAttr("_check").toBoolean();
                if (!ok) {
                    pythonReady = true;
                    llmReady = false;
                    main.post(() -> {
                        loading.set(false);
                        showFail("未检测到本地 AI 模型。\n\n" + llmHelp());
                    });
                    return;
                }

                // 4. 真正把模型加载进内存（首次需下载到内存，可能较久）
                setStatus("正在加载 AI 模型到内存（首次较慢）…");
                boolean warmed = client.callAttr("warmup").toBoolean();
                if (!warmed) {
                    pythonReady = true;
                    llmReady = false;
                    main.post(() -> {
                        loading.set(false);
                        showFail("AI 模型加载失败。\n\n" + llmHelp());
                    });
                    return;
                }

                pythonReady = true;
                llmReady = true;
                main.post(() -> {
                    loading.set(false);
                    enterChat();
                });
            } catch (Exception e) {
                android.util.Log.e("TaskReader", "init failed", e);
                main.post(() -> {
                    loading.set(false);
                    showFail("初始化失败：" + e + "\n\n请重启应用或检查设置。");
                });
            }
        }).start();
    }

    private String llmHelp() {
        return "请先在手机上安装 Ollama（Play 商店 / F-Droid），\n" +
               "拉取模型后重新加载：\n" +
               "  ollama pull qwen3:0.6b\n\n" +
               "模型就绪后点下方「重新加载」即可进入聊天。";
    }

    // ---------- 聊天界面 ----------
    @SuppressLint("SetJavaScriptEnabled")
    private void enterChat() {
        webView = new WebView(this);
        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setAllowFileAccess(true);
        s.setDomStorageEnabled(true);
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return false;
            }
        });
        webView.addJavascriptInterface(new Bridge(), "TaskReaderBridge");
        setContentView(webView);
        webView.loadUrl("file:///android_asset/index.html");
    }

    /** JS 桥：供 index.html 调用 */
    private class Bridge {

        @JavascriptInterface
        public String parse(String sentence, boolean useLlm) {
            if (!pythonReady) {
                return "{\"ok\":false,\"error\":\"引擎尚未就绪，请稍后重试\"}";
            }
            if (!llmReady) {
                return "{\"ok\":false,\"error\":\"AI 模型不可用，请重新加载\"}";
            }
            try {
                PyObject bot = Python.getInstance().getModule("bot.core").callAttr("BotCore");
                String json = bot.callAttr("handle_text_json", sentence, true).toString();
                return json;
            } catch (Exception e) {
                android.util.Log.e("TaskReader", "parse failed", e);
                return "{\"ok\":false,\"error\":\"解析失败：" + e.getMessage() + "\"}";
            }
        }

        @JavascriptInterface
        public boolean isLlmReady() {
            return llmReady;
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
