package com.aifound.app.ui;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

import com.aifound.app.R;
import com.aifound.app.net.ApiCallback;
import com.aifound.app.net.ApiClient;
import com.aifound.app.net.Models;
import com.aifound.app.util.Fmt;
import com.aifound.app.util.Steps;
import com.aifound.app.util.TabBar;
import com.google.android.material.chip.Chip;
import com.google.android.material.chip.ChipGroup;

import java.util.List;

/**
 * S08 습득물 상세 (이민서). 와이어프레임 S08_FoundDetail.
 * 서버 GET /found/{id} → 가림 처리된 사진, 상태 배지, AI 태그, 장소·일시·특징·보관 위치.
 */
public class FoundDetailActivity extends AppCompatActivity {

    private static final String EXTRA_ID = "found_id";

    public static void open(Activity from, String foundId) {
        from.startActivity(new Intent(from, FoundDetailActivity.class).putExtra(EXTRA_ID, foundId));
    }

    private Models.FoundOut item;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_found_detail);
        Steps.header(this, "습득물 상세", 0);

        String id = getIntent().getStringExtra(EXTRA_ID);
        if (id == null) {
            finish();
            return;
        }

        findViewById(R.id.btnLockerMap).setOnClickListener(v -> showLocker());
        // TODO(S16): 분실 신고 화면을 만들면 연결 (이 물건의 종류·색을 미리 채워 주면 좋음)
        findViewById(R.id.btnReportLost).setOnClickListener(v ->
                TabBar.soon(this, "분실 신고 화면은 다음 단계에서 추가돼요"));
        findViewById(R.id.btnMine).setOnClickListener(v -> explainClaim());

        ApiClient.get(this).getFound(id).enqueue(new ApiCallback<Models.FoundOut>(this) {
            @Override public void ok(Models.FoundOut body) { show(body); }
        });
    }

    private void show(Models.FoundOut f) {
        item = f;
        Fmt.photo(findViewById(R.id.ivPhoto), f.photoUrl);
        ((TextView) findViewById(R.id.tvLabel)).setText(f.displayLabel != null ? f.displayLabel : "보관 중");
        ((TextView) findViewById(R.id.tvTitle)).setText(f.title);

        // AI 태그: 종류 · 브랜드 · 색 (+ 모델, 특징)
        ChipGroup tags = findViewById(R.id.tagGroup);
        tags.removeAllViews();
        addTag(tags, "종류 · " + f.category);
        String brand = Fmt.attr(f, "brand");
        addTag(tags, "브랜드 · " + (brand != null ? brand : "확인 불가"));
        String color = Fmt.attr(f, "color");
        if (color != null) addTag(tags, "색 · " + color);
        String model = Fmt.attr(f, "model");
        if (model != null) addTag(tags, "모델 · " + model);
        Object features = f.attrs != null ? f.attrs.get("features") : null;
        if (features instanceof List) {
            for (Object o : (List<?>) features) if (o != null) addTag(tags, String.valueOf(o));
        }

        // 정보 표
        LinearLayout table = findViewById(R.id.infoTable);
        table.removeAllViews();
        addRow(table, "습득 장소", Fmt.place(f));
        addRow(table, "습득 일시", Fmt.dateTime(f.foundAt));
        addRow(table, "특징", f.description);
        if (f.locker != null) {
            addRow(table, "보관 위치", f.locker.name + (f.locker.code != null ? " (" + f.locker.code + ")" : ""));
            addRow(table, "운영 시간", f.locker.hours);
        }
        findViewById(R.id.btnLockerMap).setVisibility(f.locker != null ? View.VISIBLE : View.GONE);

        // 이미 주인에게 돌아간 물건이면 아래 버튼 끄기
        boolean returned = "returned".equals(f.status);
        findViewById(R.id.btnMine).setEnabled(!returned);
    }

    private void addTag(ChipGroup group, String text) {
        Chip chip = new Chip(this);
        chip.setText(text);
        chip.setTextSize(13);
        chip.setClickable(false);
        chip.setCheckable(false);
        chip.setChipBackgroundColorResource(R.color.white);
        chip.setChipStrokeColorResource(R.color.line);
        chip.setChipStrokeWidth(Fmt.dp(this, 1));
        chip.setEnsureMinTouchTargetSize(false);
        group.addView(chip);
    }

    private void addRow(LinearLayout table, String key, String value) {
        if (value == null || value.trim().isEmpty()) return;
        View row = LayoutInflater.from(this).inflate(R.layout.item_info_row, table, false);
        ((TextView) row.findViewById(R.id.tvKey)).setText(key);
        ((TextView) row.findViewById(R.id.tvValue)).setText(value);
        table.addView(row);
    }

    /** S09 보관함 위치. 지도 화면을 만들기 전까지는 찾아가는 길을 대화상자로 */
    private void showLocker() {
        if (item == null || item.locker == null) return;
        Models.Locker l = item.locker;
        StringBuilder msg = new StringBuilder();
        msg.append(l.building);
        if (l.location != null) msg.append("\n").append(l.location);
        if (l.hours != null) msg.append("\n\n운영 시간: ").append(l.hours);
        new AlertDialog.Builder(this)
                .setTitle(l.name)
                .setMessage(msg.toString())
                .setPositiveButton("확인", null)
                .show();
    }

    /**
     * '내 물건이에요'. 수령(S20)은 매칭(match_id)이 있어야 해서 주희선 서버와 연결이 필요하다.
     * 지금은 분실 신고 → AI 매칭 흐름을 안내한다. (팀 결정 필요: 08 에서 바로 수령 요청을 허용할지)
     */
    private void explainClaim() {
        new AlertDialog.Builder(this)
                .setTitle("내 물건인가요?")
                .setMessage("분실 신고를 남기면 AI가 이 물건과 비교해서, 일치하면 수령 방법을 알려드려요.")
                .setPositiveButton("분실 신고하기", (d, w) ->
                        TabBar.soon(this, "분실 신고 화면은 다음 단계에서 추가돼요"))
                .setNegativeButton("닫기", null)
                .show();
    }
}
