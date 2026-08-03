package com.taskreader.app;

import android.util.Log;

import com.google.ai.edge.litertlm.Backend;
import com.google.ai.edge.litertlm.Content;
import com.google.ai.edge.litertlm.Conversation;
import com.google.ai.edge.litertlm.ConversationConfig;
import com.google.ai.edge.litertlm.Engine;
import com.google.ai.edge.litertlm.EngineConfig;
import com.google.ai.edge.litertlm.Message;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Collections;

/**
 * LiteRT-LM 本地 LLM 引擎的 Java 门面（真机验证 spike）。
 *
 * 设计：纯 Java 同步调用（LiteRT-LM 的 initialize / createConversation / sendMessage
 * 均为非挂起阻塞方法，无需协程），后续可被 MainActivity 与 Python（Chaquopy 桥）共同调用。
 */
public final class LlmEngine {

    private static final String TAG = "TaskReaderLlm";

    private static volatile Engine engine;
    private static volatile String modelPath;

    private LlmEngine() {
    }

    /** 下载进度回调（主线程外调用，调用方自行切线程）。 */
    public interface DownloadProgress {
        void onProgress(long done, long total);
    }

    /** 引擎是否已初始化（模型在内存中）。 */
    public static boolean isInitialized() {
        Engine e = engine;
        return e != null && e.isInitialized();
    }

    /** 已加载的模型文件路径；未初始化返回 null。 */
    public static String getModelPath() {
        return modelPath;
    }

    /**
     * 从 URL 下载模型到 dest。支持断点续传（.part 文件）。失败抛异常。
     *
     * @param url     模型直链（如 hf-mirror 的 resolve 链接，会自动跟随重定向到 CDN）
     * @param dest    目标文件绝对路径
     * @param progress 进度回调（可为 null）
     * @return 下载完成后的文件字节数
     */
    public static long download(String url, String dest, DownloadProgress progress) throws Exception {
        File target = new File(dest);
        if (target.exists() && target.length() > 0) {
            return target.length();
        }
        File part = new File(dest + ".part");
        long existing = part.exists() ? part.length() : 0;

        HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
        conn.setInstanceFollowRedirects(true);
        conn.setRequestProperty("User-Agent", "TaskReader/0.1");
        if (existing > 0) {
            conn.setRequestProperty("Range", "bytes=" + existing + "-");
        }
        try {
            int code = conn.getResponseCode();
            if (code != HttpURLConnection.HTTP_OK && code != HttpURLConnection.HTTP_PARTIAL) {
                throw new IllegalStateException("HTTP " + code + " @ " + url);
            }
            long total = existing + Math.max(conn.getContentLengthLong(), 0);
            byte[] buf = new byte[65536];
            long done = existing;
            try (InputStream in = conn.getInputStream();
                 FileOutputStream fos = new FileOutputStream(part, true)) {
                int n;
                while ((n = in.read(buf)) > 0) {
                    fos.write(buf, 0, n);
                    done += n;
                    if (progress != null) {
                        progress.onProgress(done, total);
                    }
                }
            }
        } finally {
            conn.disconnect();
        }

        if (!part.exists() || part.length() <= 0) {
            throw new IllegalStateException("download incomplete");
        }
        if (target.exists()) {
            target.delete();
        }
        if (!part.renameTo(target)) {
            throw new IllegalStateException("rename failed: " + dest);
        }
        Log.i(TAG, "model downloaded: " + target.length() + " bytes -> " + dest);
        return target.length();
    }

    /**
     * 初始化引擎并把模型加载进内存。必须在后台线程调用（首次可能耗时数十秒）。
     *
     * @param modelPath 模型文件绝对路径
     * @param cacheDir  缓存目录（加快二次加载，可传 null）
     */
    public static synchronized void initialize(String modelPath, String cacheDir) {
        if (isInitialized()) {
            return;
        }
        EngineConfig cfg = new EngineConfig(modelPath, new Backend.CPU(4, null), null, null, null, null, cacheDir);
        Engine e = new Engine(cfg);
        e.initialize();
        engine = e;
        LlmEngine.modelPath = modelPath;
        Log.i(TAG, "engine initialized, model=" + modelPath);
    }

    /**
     * 同步推理：单轮对话，返回模型文本回复。
     *
     * @param prompt          用户输入（系统指令可并入其中）
     * @param maxOutputTokens 输出上限，防止失控生成长文本
     */
    public static synchronized String generate(String prompt, int maxOutputTokens) {
        Engine e = engine;
        if (e == null) {
            throw new IllegalStateException("engine not initialized");
        }
        Conversation conv = e.createConversation(new ConversationConfig());
        try {
            Message resp = conv.sendMessage(
                    prompt,
                    Collections.<String, Object>emptyMap(),
                    null, null, null,
                    maxOutputTokens,
                    null, null);
            StringBuilder sb = new StringBuilder();
            for (Content c : resp.getContents().getContents()) {
                if (c instanceof Content.Text) {
                    sb.append(((Content.Text) c).getText());
                }
            }
            return sb.toString();
        } finally {
            conv.close();
        }
    }

    /** 释放引擎（清空模型占用的内存）。 */
    public static synchronized void close() {
        Engine e = engine;
        if (e != null) {
            try {
                e.close();
            } catch (Exception ex) {
                Log.w(TAG, "close failed", ex);
            }
            engine = null;
            modelPath = null;
        }
    }
}
