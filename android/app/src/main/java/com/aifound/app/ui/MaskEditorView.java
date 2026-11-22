package com.aifound.app.ui;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.DashPathEffect;
import android.graphics.Paint;
import android.graphics.RectF;
import android.util.AttributeSet;
import android.view.MotionEvent;
import android.view.View;

import com.aifound.app.data.FoundDraft;

import java.util.ArrayList;
import java.util.List;

/**
 * S11 가림 편집 영역.
 * - 사진을 화면에 맞춰 그리고
 * - 확정된 가림 박스는 진한 회색으로 칠하고
 * - AI 가 감지했지만 아직 안 가린 영역은 주황 점선으로 표시
 * - '직접 가리기' 모드에서는 손가락으로 사각형을 그려 가림 박스 추가
 * 좌표는 서버와 같은 [ymin, xmin, ymax, xmax] (0~1000).
 */
public class MaskEditorView extends View {

    public interface OnChangeListener { void onMasksChanged(); }

    private Bitmap bitmap;
    private List<int[]> detected = new ArrayList<>();
    private List<int[]> masks = new ArrayList<>();
    private boolean drawMode = false;
    private OnChangeListener listener;

    private final RectF dst = new RectF();
    private RectF dragging;
    private float startX, startY;

    private final Paint maskPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint detectedPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint dragPaint = new Paint(Paint.ANTI_ALIAS_FLAG);

    public MaskEditorView(Context c) { this(c, null); }

    public MaskEditorView(Context c, AttributeSet a) {
        super(c, a);
        float d = getResources().getDisplayMetrics().density;
        maskPaint.setColor(Color.rgb(40, 40, 40));
        detectedPaint.setStyle(Paint.Style.STROKE);
        detectedPaint.setColor(Color.rgb(180, 83, 9));
        detectedPaint.setStrokeWidth(2 * d);
        detectedPaint.setPathEffect(new DashPathEffect(new float[]{6 * d, 4 * d}, 0));
        dragPaint.setStyle(Paint.Style.STROKE);
        dragPaint.setColor(Color.rgb(29, 78, 216));
        dragPaint.setStrokeWidth(2 * d);
    }

    public void setData(Bitmap bitmap, List<int[]> detected, List<int[]> masks) {
        this.bitmap = bitmap;
        this.detected = detected;
        this.masks = masks;     // FoundDraft 의 리스트를 그대로 공유
        invalidate();
    }

    public void setDrawMode(boolean on) { drawMode = on; }

    public boolean isDrawMode() { return drawMode; }

    public void setOnChangeListener(OnChangeListener l) { listener = l; }

    public void refresh() { invalidate(); }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        if (bitmap == null) return;
        // fitCenter 계산
        float vw = getWidth(), vh = getHeight();
        float scale = Math.min(vw / bitmap.getWidth(), vh / bitmap.getHeight());
        float w = bitmap.getWidth() * scale, h = bitmap.getHeight() * scale;
        dst.set((vw - w) / 2f, (vh - h) / 2f, (vw + w) / 2f, (vh + h) / 2f);

        canvas.drawBitmap(bitmap, null, dst, null);
        for (int[] m : masks) canvas.drawRect(toView(m), maskPaint);
        for (int[] d : detected) {
            if (FoundDraft.coverage(d, masks) < 0.8) canvas.drawRect(toView(d), detectedPaint);
        }
        if (dragging != null) canvas.drawRect(dragging, dragPaint);
    }

    private RectF toView(int[] b) {
        return new RectF(
                dst.left + b[1] / 1000f * dst.width(),
                dst.top + b[0] / 1000f * dst.height(),
                dst.left + b[3] / 1000f * dst.width(),
                dst.top + b[2] / 1000f * dst.height());
    }

    private int[] toNorm(RectF r) {
        int xmin = clamp((r.left - dst.left) / dst.width() * 1000f);
        int ymin = clamp((r.top - dst.top) / dst.height() * 1000f);
        int xmax = clamp((r.right - dst.left) / dst.width() * 1000f);
        int ymax = clamp((r.bottom - dst.top) / dst.height() * 1000f);
        return new int[]{ymin, xmin, ymax, xmax};
    }

    private static int clamp(float v) { return Math.max(0, Math.min(1000, Math.round(v))); }

    @Override
    public boolean onTouchEvent(MotionEvent e) {
        if (!drawMode || bitmap == null) return super.onTouchEvent(e);
        float x = Math.max(dst.left, Math.min(dst.right, e.getX()));
        float y = Math.max(dst.top, Math.min(dst.bottom, e.getY()));
        switch (e.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                startX = x;
                startY = y;
                dragging = new RectF(x, y, x, y);
                getParent().requestDisallowInterceptTouchEvent(true);
                invalidate();
                return true;
            case MotionEvent.ACTION_MOVE:
                if (dragging != null) {
                    dragging.set(Math.min(startX, x), Math.min(startY, y), Math.max(startX, x), Math.max(startY, y));
                    invalidate();
                }
                return true;
            case MotionEvent.ACTION_UP:
                if (dragging != null && dragging.width() > 12 && dragging.height() > 12) {
                    masks.add(toNorm(dragging));
                    if (listener != null) listener.onMasksChanged();
                }
                dragging = null;
                invalidate();
                performClick();
                return true;
            case MotionEvent.ACTION_CANCEL:
                dragging = null;
                invalidate();
                return true;
            default:
                return true;
        }
    }

    @Override
    public boolean performClick() { return super.performClick(); }
}
