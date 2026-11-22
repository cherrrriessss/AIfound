package com.aifound.app.data;

import com.aifound.app.net.Models;

import java.io.File;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Calendar;
import java.util.List;

/**
 * 습득물 등록 5단계(S10~S14) 동안 입력값을 모아 두는 곳.
 * 화면을 넘어가도 값이 유지되고, 마지막 '등록하기'에서 한 번에 서버로 보낸다.
 */
public final class FoundDraft {
    private static FoundDraft current = new FoundDraft();

    public static FoundDraft get() { return current; }

    public static void reset() { current = new FoundDraft(); }

    // S10 사진 (가로세로 1600px 이하 JPEG, EXIF 제거됨)
    public File imageFile;
    // S10→S11 AI 분석 결과
    public Models.AnalyzeOut analysis;
    // S11 가림 박스 [ymin, xmin, ymax, xmax] (0~1000)
    public final List<int[]> masks = new ArrayList<>();
    // S12 사용자가 확인/수정한 속성
    public Models.ItemAttributes attributes;
    // S13
    public String building;
    public String locationDetail;
    public Calendar foundAt = Calendar.getInstance();
    public String description;
    // S14
    public String lockerId;
    public String lockerName;
    // S15
    public Models.FoundOut result;

    /** AI 가 찾은 개인정보 영역 */
    public List<int[]> detectedRegions() {
        List<int[]> out = new ArrayList<>();
        if (attributes == null || attributes.piiRegions == null) return out;
        for (Models.PiiRegion r : attributes.piiRegions) {
            if (r.box != null && r.box.size() == 4) {
                out.add(new int[]{r.box.get(0), r.box.get(1), r.box.get(2), r.box.get(3)});
            }
        }
        return out;
    }

    /** 감지 영역 중 80% 이상 가려지지 않은 것 (서버와 같은 기준) */
    public List<int[]> uncoveredRegions() {
        List<int[]> left = new ArrayList<>();
        for (int[] d : detectedRegions()) {
            if (coverage(d, masks) < 0.8) left.add(d);
        }
        return left;
    }

    public static double coverage(int[] d, List<int[]> masks) {
        double area = Math.max(1, (double) (d[2] - d[0]) * (d[3] - d[1]));
        double covered = 0;
        for (int[] m : masks) {
            int iy = Math.max(0, Math.min(d[2], m[2]) - Math.max(d[0], m[0]));
            int ix = Math.max(0, Math.min(d[3], m[3]) - Math.max(d[1], m[1]));
            covered += (double) iy * ix;
        }
        return Math.min(1.0, covered / area);
    }

    public List<Models.MaskBox> maskBoxes() {
        List<Models.MaskBox> out = new ArrayList<>();
        for (int[] m : masks) out.add(new Models.MaskBox(Arrays.asList(m[0], m[1], m[2], m[3])));
        return out;
    }
}
