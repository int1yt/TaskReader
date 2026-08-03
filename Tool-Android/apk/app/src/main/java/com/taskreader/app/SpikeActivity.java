package com.taskreader.app;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.StatFs;
import android.text.InputType;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * LiteRT-LM 真机验证 Spike（临时启动页）。
 *
 * 模型只下载一次、只初始化一次（文件与引擎都持久保留），之后每次只做推理：
 *   「输入句子 → 规则引擎 + LLM 混合 → 最终任务分解结果」
 * 最终结果来自 task_reader/bot.core 的完整管线（规则负责准确的时间/日期归一化，
 * LLM 在规则不足时兜底并融合），屏幕上只打印干净的结构化结果。
 */
public class SpikeActivity extends Activity {

    private static final String MODEL_URL =
            "https://hf-mirror.com/litert-community/Qwen3-0.6B/resolve/main/qwen3_0_6b_mixed_int4.litertlm";
    private static final String MODEL_NAME = "qwen3_0_6b_mixed_int4.litertlm";
    private static final String SAMPLE_SENTENCE = "我下周三要交论文，周五下午三点去图书馆借书，顺便去菜市场买菜";

    private final Handler main = new Handler(Looper.getMainLooper());

    private EditText inputBox;
    private TextView logView;
    private ScrollView scroll;
    private Button runButton;
    private Button inferButton;
    private volatile boolean running = false;
    private volatile boolean envLogged = false;
    private volatile boolean jiebaReady = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        buildUi();
        logLine("=== 任务提取 · 本地 LLM 真机验证 ===");
        logLine("模型只需下载/加载一次；输入句子点「开始测试」即出最终结果。");
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(16), dp(16), dp(16), dp(16));

        TextView title = new TextView(this);
        title.setText("任务提取 · 规则 + 本地 LLM");
        title.setTextSize(17);
        title.setGravity(Gravity.CENTER);
        root.addView(title);

        inputBox = new EditText(this);
        inputBox.setHint("输入要检测任务的句子，如：" + SAMPLE_SENTENCE);
        inputBox.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        inputBox.setMinLines(2);
        inputBox.setMaxLines(4);
        inputBox.setTextSize(14);
        inputBox.setText(SAMPLE_SENTENCE);
        root.addView(inputBox, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout btnRow = new LinearLayout(this);
        btnRow.setOrientation(LinearLayout.HORIZONTAL);
        btnRow.setGravity(Gravity.CENTER);

        runButton = new Button(this);
        runButton.setText("开始测试");
        runButton.setOnClickListener(v -> startTest());
        btnRow.addView(runButton, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));

        inferButton = new Button(this);
        inferButton.setText("用输入语句推理");
        inferButton.setOnClickListener(v -> runDirect());
        btnRow.addView(inferButton, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));

        root.addView(btnRow, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        scroll = new ScrollView(this);
        logView = new TextView(this);
        logView.setTextSize(12);
        logView.setTypeface(android.graphics.Typeface.MONOSPACE);
        logView.setLineSpacing(dp(2), 1f);
        logView.setTextColor(0xFF222222);
        scroll.addView(logView, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        root.addView(scroll, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));
        setContentView(root);
    }

    private int dp(int v) {
        return (int) (v * getResources().getDisplayMetrics().density + 0.5f);
    }

    private void logLine(String s) {
        main.post(() -> {
            String stamp = new SimpleDateFormat("HH:mm:ss", Locale.US).format(new Date());
            String prev = logView.getText().toString();
            logView.setText(prev + (prev.isEmpty() ? "" : "\n") + "[" + stamp + "] " + s);
            scroll.post(() -> scroll.fullScroll(View.FOCUS_DOWN));
        });
    }

    private String currentSentence() {
        String s = inputBox.getText().toString().trim();
        if (s.isEmpty()) {
            logLine("（未输入句子，请先在输入框填写内容）");
            return null;
        }
        return s;
    }

    /** 开始测试：确保模型已下载 + 引擎已初始化，然后对输入句子跑完整管线。 */
    private void startTest() {
        if (running) return;
        String sentence = currentSentence();
        if (sentence == null) return;
        running = true;
        setButtons(false);
        new Thread(() -> {
            try {
                File dir = new File(getFilesDir(), "models");
                if (!dir.exists()) dir.mkdirs();
                File model = new File(dir, MODEL_NAME);

                logEnv();

                // 1) 模型只下载一次：已存在且完整则跳过，绝不删除重下
                if (!model.exists() || model.length() < 1024 * 1024) {
                    logLine("首次使用：下载模型 (~474MB) ...");
                    long t0 = System.currentTimeMillis();
                    final int[] lastPct = {-1};
                    LlmEngine.download(MODEL_URL, model.getAbsolutePath(), (done, total) -> {
                        int pct = total > 0 ? (int) (done * 100 / total) : -1;
                        if (pct != lastPct[0] && pct >= 0) {
                            lastPct[0] = pct;
                            logLine("  下载 " + pct + "%  (" + mb(done) + "MB / " + mb(total) + "MB)");
                        }
                    });
                    logLine("下载完成: " + mb(model.length()) + "MB, 耗时 "
                            + (System.currentTimeMillis() - t0) / 1000 + "s");
                } else {
                    logLine("模型已存在，跳过下载: " + mb(model.length()) + "MB");
                }

                // 2) 引擎只初始化一次：已在内存则跳过
                if (!LlmEngine.isInitialized()) {
                    logLine("初始化引擎（模型加载进内存）...");
                    long t0 = System.currentTimeMillis();
                    LlmEngine.initialize(model.getAbsolutePath(), getCacheDir().getAbsolutePath());
                    logLine("初始化完成: 耗时 " + (System.currentTimeMillis() - t0) / 1000 + "s");
                } else {
                    logLine("引擎已在内存，跳过初始化");
                }

                ensureJieba();
                parseOnce(sentence);
                logLine("=== 完成。可直接改输入框句子再点「用输入语句推理」 ===");
            } catch (Exception e) {
                android.util.Log.e("TaskReaderSpike", "start failed", e);
                logLine("!!! 失败: " + e);
            } finally {
                running = false;
                main.post(() -> setButtons(true));
            }
        }).start();
    }

    /** 用输入语句推理：引擎已就绪时直接跑管线，不下载不初始化。 */
    private void runDirect() {
        if (running) return;
        String sentence = currentSentence();
        if (sentence == null) return;
        if (!LlmEngine.isInitialized()) {
            logLine("引擎尚未初始化，请先点「开始测试」。");
            return;
        }
        running = true;
        setButtons(false);
        new Thread(() -> {
            try {
                ensureJieba();
                parseOnce(sentence);
            } catch (Exception e) {
                android.util.Log.e("TaskReaderSpike", "infer failed", e);
                logLine("!!! 推理失败: " + e);
            } finally {
                running = false;
                main.post(() -> setButtons(true));
            }
        }).start();
    }

    private void setButtons(boolean enabled) {
        runButton.setEnabled(enabled);
        inferButton.setEnabled(enabled);
    }

    private void ensureJieba() {
        if (jiebaReady) return;
        logLine("预热分词引擎（首次较慢）...");
        Python.getInstance().getModule("jieba").callAttr("initialize");
        jiebaReady = true;
    }

    private void logEnv() {
        if (envLogged) return;
        envLogged = true;
        logLine("设备: " + Build.MODEL + " | " + Build.SUPPORTED_ABIS[0]
                + " | API " + Build.VERSION.SDK_INT + " | RAM " + totalRamMb() + "MB");
        logLine("可用存储: " + mb(freeBytes(getFilesDir())) + "MB");
    }

    /** 跑完整管线：规则 + LLM 混合 → 打印最终任务分解结果。 */
    private void parseOnce(String sentence) {
        logLine("--- 处理输入 ---");
        logLine("输入: " + sentence);
        long t0 = System.currentTimeMillis();
        String json;
        try {
            // callAttr 已调用类构造器返回实例，勿再 .call()
            PyObject inst = Python.getInstance().getModule("bot.core")
                    .callAttr("BotCore");
            json = inst.callAttr("handle_text_json", sentence, true).toString();
        } catch (Exception e) {
            android.util.Log.e("TaskReaderSpike", "parse failed", e);
            logLine("  解析异常: " + e);
            return;
        }
        double dt = (System.currentTimeMillis() - t0) / 1000.0;
        renderReply(json, dt);
    }

    /** 把 handle_text_json 的回复渲染成干净的任务列表：任务 + 截止时间 + 描述 + 其他备注。 */
    private void renderReply(String json, double dt) {
        try {
            JSONObject obj = new JSONObject(json);
            boolean ok = obj.optBoolean("ok", false);
            if (!ok) {
                logLine("  引擎返回错误: " + obj.optString("error", json));
                return;
            }
            String source = obj.optString("source", "rule");
            boolean usedLlm = source.contains("llm");
            JSONArray tasks = obj.optJSONArray("tasks");

            logLine("来源: " + source + (usedLlm ? "（本地 LLM 融合）" : "（规则引擎）")
                    + " | 耗时: " + String.format(Locale.US, "%.2f", dt) + "s");

            if (tasks == null || tasks.length() == 0) {
                logLine("未识别到任务。");
                return;
            }
            for (int i = 0; i < tasks.length(); i++) {
                JSONObject t = tasks.getJSONObject(i);

                logLine("[任务" + (i + 1) + "] " + t.optString("task", "任务"));

                // 时间：区分 时间范围 / 截止时间 / 点时间(=开始时间)，只按原文给约束，不多不少
                String time = t.optString("time", "");
                String ts = t.optString("time_start", "");
                String te = t.optString("time_end", "");
                String timeText = t.optString("time_text", "");
                if (!ts.isEmpty() && !te.isEmpty() && !ts.equals(te)) {
                    // 时间范围：3点到5点 → 有开始有结束
                    logLine("   时间范围: " + ts + " ~ " + te
                            + (timeText.isEmpty() ? "" : "（" + timeText + "）"));
                } else if (!te.isEmpty() && ts.isEmpty()) {
                    // 截止时间：周五之前 → 只有结束界
                    logLine("   截止时间: " + te
                            + (timeText.isEmpty() ? "" : "（" + timeText + "）"));
                } else if (!ts.isEmpty()) {
                    // 点时间：周五下午三点 → 开始时间
                    logLine("   开始时间: " + ts
                            + (timeText.isEmpty() ? "" : "（" + timeText + "）"));
                } else if (!time.isEmpty()) {
                    logLine("   时间: " + time
                            + (timeText.isEmpty() ? "" : "（" + timeText + "）"));
                }

                // 描述：动作 + 对象
                String act = t.optString("action", "");
                String objv = t.optString("object", "");
                if (!act.isEmpty() || !objv.isEmpty()) {
                    StringBuilder ds = new StringBuilder();
                    if (!act.isEmpty()) ds.append(act);
                    if (!objv.isEmpty()) ds.append(ds.length() == 0 ? objv : " " + objv);
                    logLine("   描述: " + ds);
                }

                // 其他备注：地点 + 附加说明
                StringBuilder nt = new StringBuilder();
                String place = t.optString("place", "");
                String notes = t.optString("notes", "");
                if (!place.isEmpty()) nt.append(place);
                if (!notes.isEmpty()) nt.append(nt.length() == 0 ? notes : "；" + notes);
                if (nt.length() > 0) logLine("   其他备注: " + nt);

                double conf = t.optDouble("confidence", -1);
                String src = t.optString("source", "");
                if (conf >= 0) logLine("   (置信度 " + String.format(Locale.US, "%.0f%%", conf * 100)
                        + " · " + src + ")");
            }
        } catch (Exception e) {
            logLine("  结果渲染失败: " + e + "\n  原始: " + truncate(json, 300));
        }
    }

    private static String truncate(String s, int max) {
        if (s == null) return "null";
        return s.length() <= max ? s : s.substring(0, max) + "...";
    }

    private static String mb(long bytes) {
        return String.format(Locale.US, "%.1f", bytes / 1048576.0);
    }

    private static long freeBytes(File dir) {
        try {
            StatFs sf = new StatFs(dir.getAbsolutePath());
            return sf.getAvailableBytes();
        } catch (Exception e) {
            return -1;
        }
    }

    private static long totalRamMb() {
        try {
            java.io.FileReader fr = new java.io.FileReader("/proc/meminfo");
            java.io.BufferedReader br = new java.io.BufferedReader(fr);
            String line = br.readLine();
            br.close();
            if (!TextUtils.isEmpty(line)) {
                String[] p = line.trim().split("\\s+");
                if (p.length >= 2) return Long.parseLong(p[1]) / 1024;
            }
        } catch (Exception ignored) {
        }
        return -1;
    }

    @SuppressLint("MissingSuperCall")
    @Override
    public void onBackPressed() {
        finishAffinity();
    }
}
