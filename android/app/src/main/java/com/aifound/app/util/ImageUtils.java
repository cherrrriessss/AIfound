package com.aifound.app.util;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Matrix;
import android.net.Uri;

import androidx.exifinterface.media.ExifInterface;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;

/** 사진 준비: 회전 바로잡기 → 1600px 로 줄이기 → JPEG 저장(EXIF 위치정보 없음). */
public final class ImageUtils {
    public static final int MAX_SIDE = 1600;

    private ImageUtils() {}

    public static File prepareJpeg(Context ctx, Uri src) throws IOException {
        // 1) 크기만 먼저 읽어서 메모리 절약용 축소 배율 계산
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        try (InputStream in = open(ctx, src)) {
            BitmapFactory.decodeStream(in, null, bounds);
        }
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) throw new IOException("사진을 읽을 수 없어요.");
        int sample = 1;
        while (Math.max(bounds.outWidth, bounds.outHeight) / (sample * 2) >= MAX_SIDE) sample *= 2;

        // 2) 실제 디코딩
        BitmapFactory.Options opts = new BitmapFactory.Options();
        opts.inSampleSize = sample;
        Bitmap bmp;
        try (InputStream in = open(ctx, src)) {
            bmp = BitmapFactory.decodeStream(in, null, opts);
        }
        if (bmp == null) throw new IOException("사진을 읽을 수 없어요.");

        // 3) 폰 사진의 회전 정보 반영
        int rotation = 0;
        try (InputStream in = open(ctx, src)) {
            rotation = new ExifInterface(in).getRotationDegrees();
        } catch (IOException ignored) {
            // 회전 정보가 없으면 그대로
        }
        if (rotation != 0) {
            Matrix m = new Matrix();
            m.postRotate(rotation);
            bmp = Bitmap.createBitmap(bmp, 0, 0, bmp.getWidth(), bmp.getHeight(), m, true);
        }

        // 4) 긴 변 1600px 이하로
        int w = bmp.getWidth(), h = bmp.getHeight();
        float scale = MAX_SIDE / (float) Math.max(w, h);
        if (scale < 1f) {
            bmp = Bitmap.createScaledBitmap(bmp, Math.round(w * scale), Math.round(h * scale), true);
        }

        // 5) 새 JPEG 로 저장 → 원본 EXIF(GPS 등)는 따라오지 않는다
        File out = new File(ctx.getCacheDir(), "found_draft.jpg");
        try (FileOutputStream fos = new FileOutputStream(out)) {
            bmp.compress(Bitmap.CompressFormat.JPEG, 88, fos);
        }
        return out;
    }

    public static Bitmap load(File file) {
        return BitmapFactory.decodeFile(file.getAbsolutePath());
    }

    /** 미리보기용: 가림 박스([ymin, xmin, ymax, xmax], 0~1000)를 칠한 사본 */
    public static Bitmap masked(Bitmap src, java.util.List<int[]> masks) {
        if (src == null) return null;
        Bitmap out = src.copy(Bitmap.Config.ARGB_8888, true);
        android.graphics.Canvas canvas = new android.graphics.Canvas(out);
        android.graphics.Paint paint = new android.graphics.Paint();
        paint.setColor(android.graphics.Color.rgb(40, 40, 40));
        int w = out.getWidth(), h = out.getHeight();
        for (int[] m : masks) {
            canvas.drawRect(m[1] / 1000f * w, m[0] / 1000f * h, m[3] / 1000f * w, m[2] / 1000f * h, paint);
        }
        return out;
    }

    private static InputStream open(Context ctx, Uri uri) throws IOException {
        InputStream in = ctx.getContentResolver().openInputStream(uri);
        if (in == null) throw new IOException("사진을 열 수 없어요.");
        return in;
    }
}
