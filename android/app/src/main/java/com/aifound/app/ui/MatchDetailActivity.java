package com.aifound.app.ui;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.CheckBox;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

import com.aifound.app.R;
import com.aifound.app.net.ApiCallback;
import com.aifound.app.net.ApiClient;
import com.aifound.app.net.MatchModels;
import com.aifound.app.net.Models;
import com.aifound.app.util.Fmt;
import com.aifound.app.util.Ui;
import com.google.android.material.bottomsheet.BottomSheetDialog;
import com.google.android.material.button.MaterialButton;

import java.util.ArrayList;
import java.util.List;

/**
 * S19 매칭 상세 (이민서). 와이어프레임 S19_MatchDetail.
 * GET /matches/{id} → 내 신고 vs 습득물, 일치율, AI가 찾은 이유, 점수 구성(속성·의미·장소·시간), 보관 위치.
 * '내 물건이에요' → POST /matches/{id}/claim → S20 수령 안내
 * '내 물건 아니에요' → S21 시트 → POST /matches/{id}/reject
 * 05 푸시·27 알림함에서도 match_id 로 바로 이 화면을 연다.
 */
public class MatchDetailActivity extends AppCompatActivity {

    private static final String EXTRA_ID = "match_id";

    public static void open(Activity from, String matchId) {
        from.startActivity(intent(from, matchId));
    }

    /** S05 푸시를 눌렀을 때도 같은 화면 (util/Push) */
    public static Intent intent(android.content.Context c, String matchId) {
        return new Intent(c, MatchDetailActivity.class).putExtra(EXTRA_ID, matchId);
    }

    private String matchId;
    private MatchModels.MatchDetail detail;
    private MaterialButton btnMine, btnNotMine;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_match_detail);
        Ui.header(this, "매칭 상세");
        matchId = getIntent().getStringExtra(EXTRA_ID);
        if (matchId == null) {
            finish();
            return;
        }
        btnMine = findViewById(R.id.btnMine);
        btnNotMine = findViewById(R.id.btnNotMine);
        btnMine.setOnClickListener(v -> onMine());
        btnNotMine.setOnClickListener(v -> showNotMineSheet());
        findViewById(R.id.btnLockerMap).setOnClickListener(v -> openLocker());
        findViewById(R.id.foundCol).setOnClickListener(v -> {
            if (detail != null && detail.foundItem != null) FoundDetailActivity.open(this, detail.foundItem.id);
        });
    }

    @Override
    protected void onResume() {
        super.onResume();
        ApiClient.match(this).matchDetail(matchId).enqueue(new ApiCallback<MatchModels.MatchDetail>(this) {
            @Override public void ok(MatchModels.MatchDetail body) { show(body); }
        });
    }

    private void show(MatchModels.MatchDetail d) {
        detail = d;
        MatchModels.ReportInfo r = d.myReport;
        MatchModels.FoundInfo f = d.foundItem;

        // 내 신고
        ImageView ivReport = findViewById(R.id.ivReport);
        Fmt.photo(ivReport, r != null ? r.photoUrl : null);
        findViewById(R.id.tvNoReportPhoto).setVisibility(r != null && r.photoUrl != null ? View.GONE : View.VISIBLE);
        if (r != null) {
            ((TextView) findViewById(R.id.tvReport)).setText(attrLine(r.attrs) + "\n"
                    + Fmt.join(r.buildings, ", ") + " · " + Fmt.lostRange(r.lostFrom, r.lostTo));
        }
        // 습득물
        if (f != null) {
            Fmt.photo(findViewById(R.id.ivFound), f.photoUrl);
            ((TextView) findViewById(R.id.tvFound)).setText(attrLine(f.attrs) + "\n"
                    + Fmt.place(f.building, f.locationDetail) + " · " + Fmt.dateTimePlain(f.foundAt));
        }

        // 일치율 + 이유. 08 에서 직접 수령 요청한 건은 AI 점수가 없다
        TextView score = findViewById(R.id.tvScore);
        if (d.direct) {
            score.setVisibility(View.GONE);
            ((TextView) findViewById(R.id.tvReasonTitle)).setText("직접 수령 요청");
            ((TextView) findViewById(R.id.tvReason)).setText("습득물 상세에서 '내 물건이에요'를 눌러 만든 요청이에요. 행정실에서 학교 메일로 본인 확인을 해요.");
            findViewById(R.id.breakdownBox).setVisibility(View.GONE);
        } else {
            score.setText(d.score + "%");
            ((TextView) findViewById(R.id.tvReason)).setText(d.reason);
            showBreakdown(d.breakdown);
        }

        // 보관 위치
        MatchModels.LockerInfo l = f != null ? f.lockers : null;
        findViewById(R.id.lockerRow).setVisibility(l != null ? View.VISIBLE : View.GONE);
        if (l != null) ((TextView) findViewById(R.id.tvLocker)).setText("보관: " + l.name);

        // 상태에 따라 아래 버튼
        boolean claimed = "claimed".equals(d.status) || "received".equals(d.status);
        boolean closed = "closed".equals(d.status) || "rejected".equals(d.status);
        btnNotMine.setVisibility(claimed || closed ? View.GONE : View.VISIBLE);
        if ("received".equals(d.status)) {
            btnMine.setText("수령 완료된 물건이에요");
            btnMine.setEnabled(false);
        } else if (claimed) {
            btnMine.setText("수령 안내 보기");
            btnMine.setEnabled(true);
        } else if (closed) {
            btnMine.setText("rejected".equals(d.status) ? "후보에서 제외했어요" : "다른 사람이 수령했어요");
            btnMine.setEnabled(false);
        } else {
            btnMine.setText("내 물건이에요");
            btnMine.setEnabled(true);
        }
    }

    /** '검정 · Apple · 이어폰' */
    private static String attrLine(java.util.Map<String, Object> a) {
        List<String> parts = new ArrayList<>();
        parts.add(Fmt.attr(a, "color"));
        String model = Fmt.attr(a, "model");
        parts.add(model != null ? model : Fmt.attr(a, "brand"));
        parts.add(Fmt.attr(a, "category"));
        return Fmt.join(parts, " · ");
    }

    private void showBreakdown(List<MatchModels.Bar> bars) {
        LinearLayout box = findViewById(R.id.breakdown);
        box.removeAllViews();
        LayoutInflater inf = LayoutInflater.from(this);
        for (MatchModels.Bar b : bars) {
            View row = inf.inflate(R.layout.item_score_bar, box, false);
            ((TextView) row.findViewById(R.id.tvLabel)).setText(b.label + " " + b.max);
            ProgressBar bar = row.findViewById(R.id.bar);
            bar.setMax(Math.max(1, b.max));
            bar.setProgress(b.value);
            ((TextView) row.findViewById(R.id.tvValue)).setText(String.valueOf(b.value));
            row.setContentDescription(b.label + " " + b.max + "점 중 " + b.value + "점");
            box.addView(row);
        }
    }

    private void openLocker() {
        if (detail == null || detail.foundItem == null || detail.foundItem.lockers == null) return;
        StorageMapActivity.open(this, detail.foundItem.lockers);
    }

    // ---------------- 내 물건이에요 → S20 ----------------

    private void onMine() {
        if (detail == null) return;
        if ("claimed".equals(detail.status)) {
            ClaimActivity.open(this, matchId);
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("내 물건이 맞나요?")
                .setMessage("수령 대기로 바뀌고 7일 안에 보관함에서 찾아가야 해요.\n습득자에게 '주인이 확인했어요' 알림이 가요.")
                .setPositiveButton("네, 맞아요", (dlg, w) -> claim())
                .setNegativeButton("취소", null)
                .show();
    }

    private void claim() {
        btnMine.setEnabled(false);
        ApiClient.match(this).claim(matchId).enqueue(new ApiCallback<MatchModels.ClaimOut>(this) {
            @Override public void ok(MatchModels.ClaimOut body) {
                ClaimActivity.open(MatchDetailActivity.this, matchId);
            }

            @Override public void fail(String message) {
                super.fail(message);
                btnMine.setEnabled(true);
            }
        });
    }

    // ---------------- S21 내 물건 아니에요 ----------------

    private void showNotMineSheet() {
        BottomSheetDialog sheet = new BottomSheetDialog(this);
        View v = LayoutInflater.from(this).inflate(R.layout.sheet_not_mine, null);
        sheet.setContentView(v);
        v.findViewById(R.id.btnSkip).setOnClickListener(x -> {
            sheet.dismiss();
            reject(new ArrayList<>());
        });
        v.findViewById(R.id.btnSend).setOnClickListener(x -> {
            List<String> reasons = new ArrayList<>();
            addIf(v, R.id.cbCategory, "category", reasons);
            addIf(v, R.id.cbColor, "color", reasons);
            addIf(v, R.id.cbBrand, "brand_model", reasons);
            addIf(v, R.id.cbPlace, "place_time", reasons);
            addIf(v, R.id.cbOther, "other", reasons);
            sheet.dismiss();
            reject(reasons);
        });
        sheet.show();
    }

    private static void addIf(View root, int id, String reason, List<String> out) {
        if (((CheckBox) root.findViewById(id)).isChecked()) out.add(reason);
    }

    /** 건너뛰기도 '후보에서 제외'는 한다 (이유만 비워서) — 매칭 서버 README 21 */
    private void reject(List<String> reasons) {
        MatchModels.RejectIn body = new MatchModels.RejectIn();
        body.reasons = reasons;
        ApiClient.match(this).reject(matchId, body).enqueue(new ApiCallback<Models.Ok>(this) {
            @Override public void ok(Models.Ok ok) {
                Toast.makeText(MatchDetailActivity.this,
                        reasons.isEmpty() ? "후보에서 제외했어요" : "알려주셔서 고마워요. 후보에서 제외했어요",
                        Toast.LENGTH_SHORT).show();
                finish();
            }
        });
    }
}
