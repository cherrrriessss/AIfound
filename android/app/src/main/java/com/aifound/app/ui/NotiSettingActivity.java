package com.aifound.app.ui;

import android.app.TimePickerDialog;
import android.graphics.Typeface;
import android.os.Bundle;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.style.AbsoluteSizeSpan;
import android.text.style.ForegroundColorSpan;
import android.text.style.StyleSpan;
import android.view.View;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.aifound.app.R;
import com.aifound.app.net.ApiCallback;
import com.aifound.app.net.ApiClient;
import com.aifound.app.net.MatchModels;
import com.aifound.app.util.Ui;
import com.google.android.material.button.MaterialButton;
import com.google.android.material.chip.Chip;
import com.google.android.material.chip.ChipGroup;
import com.google.android.material.materialswitch.MaterialSwitch;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * S26 알림 설정 (이민서). 와이어프레임 S26_NotiSetting.
 * 매칭 서버 GET/PUT /settings/notifications: match_alert, owner_alert, pickup_reminder,
 * interest_buildings, quiet_start/quiet_end ('23:00'). 바꿀 때마다 바로 저장한다.
 */
public class NotiSettingActivity extends AppCompatActivity {

    private MaterialSwitch swMatch, swOwner, swReminder, swQuiet;
    private ChipGroup buildingGroup;
    private MaterialButton btnStart, btnEnd;
    private String quietStart = "23:00", quietEnd = "08:00";
    private final Set<String> interest = new LinkedHashSet<>();
    private boolean loading = true;      // 처음 값 채울 때는 저장하지 않기

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_noti_setting);
        Ui.header(this, "알림 설정");
        swMatch = findViewById(R.id.swMatch);
        swOwner = findViewById(R.id.swOwner);
        swReminder = findViewById(R.id.swReminder);
        swQuiet = findViewById(R.id.swQuiet);
        buildingGroup = findViewById(R.id.buildingGroup);
        btnStart = findViewById(R.id.btnQuietStart);
        btnEnd = findViewById(R.id.btnQuietEnd);
        for (MaterialSwitch sw : new MaterialSwitch[]{swMatch, swOwner, swReminder, swQuiet}) {
            sw.setText(twoLine(sw.getText().toString()));
        }

        swMatch.setOnCheckedChangeListener((b, on) -> save());
        swOwner.setOnCheckedChangeListener((b, on) -> save());
        swReminder.setOnCheckedChangeListener((b, on) -> save());
        swQuiet.setOnCheckedChangeListener((b, on) -> {
            findViewById(R.id.quietRow).setVisibility(on ? View.VISIBLE : View.GONE);
            save();
        });
        btnStart.setOnClickListener(v -> pickTime(true));
        btnEnd.setOnClickListener(v -> pickTime(false));

        ApiClient.match(this).settings().enqueue(new ApiCallback<MatchModels.Settings>(this) {
            @Override public void ok(MatchModels.Settings s) {
                fill(s);
                loadBuildings();
            }
        });
    }

    /** '제목\n설명' → 제목은 굵게, 설명은 작은 회색 */
    private CharSequence twoLine(String text) {
        int nl = text.indexOf('\n');
        SpannableString sp = new SpannableString(text);
        if (nl < 0) return sp;
        sp.setSpan(new StyleSpan(Typeface.BOLD), 0, nl, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        sp.setSpan(new AbsoluteSizeSpan(12, true), nl + 1, text.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        sp.setSpan(new ForegroundColorSpan(getColor(R.color.ink_quiet)), nl + 1, text.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        return sp;
    }

    private void fill(MatchModels.Settings s) {
        loading = true;
        swMatch.setChecked(s.matchAlert == null || s.matchAlert);
        swOwner.setChecked(s.ownerAlert == null || s.ownerAlert);
        swReminder.setChecked(s.pickupReminder != null && s.pickupReminder);
        // 서버 규칙: 시작 == 끝이면 방해 금지 없음 (alerts.in_quiet_hours)
        boolean quiet = s.quietStart != null && s.quietEnd != null && !hhmm(s.quietStart).equals(hhmm(s.quietEnd));
        if (quiet) {
            quietStart = hhmm(s.quietStart);
            quietEnd = hhmm(s.quietEnd);
        }
        swQuiet.setChecked(quiet);
        findViewById(R.id.quietRow).setVisibility(quiet ? View.VISIBLE : View.GONE);
        showQuiet();
        interest.clear();
        if (s.interestBuildings != null) interest.addAll(s.interestBuildings);
        loading = false;
    }

    /** '23:00:00' → '23:00' */
    private static String hhmm(String t) {
        return t.length() >= 5 ? t.substring(0, 5) : t;
    }

    private void showQuiet() {
        btnStart.setText(quietStart);
        btnEnd.setText(quietEnd);
    }

    private void pickTime(boolean start) {
        String cur = start ? quietStart : quietEnd;
        int h = Integer.parseInt(cur.substring(0, 2)), m = Integer.parseInt(cur.substring(3, 5));
        new TimePickerDialog(this, (tp, hh, mm) -> {
            String v = String.format(java.util.Locale.US, "%02d:%02d", hh, mm);
            if (start) quietStart = v;
            else quietEnd = v;
            showQuiet();
            save();
        }, h, m, true).show();
    }

    private void loadBuildings() {
        ApiClient.get(this).buildings().enqueue(new ApiCallback<List<String>>(this) {
            @Override public void ok(List<String> all) {
                buildingGroup.removeAllViews();
                for (String b : all) {
                    Chip chip = Ui.choiceChip(NotiSettingActivity.this, buildingGroup, b);
                    chip.setChecked(interest.contains(b));
                    chip.setOnCheckedChangeListener((c, on) -> {
                        if (on) interest.add(b);
                        else interest.remove(b);
                        save();
                    });
                }
                if (all.isEmpty()) buildingGroup.addView(Ui.empty(NotiSettingActivity.this, "건물 목록이 비어 있어요"));
            }
        });
    }

    private void save() {
        if (loading) return;
        MatchModels.Settings body = new MatchModels.Settings();
        body.matchAlert = swMatch.isChecked();
        body.ownerAlert = swOwner.isChecked();
        body.pickupReminder = swReminder.isChecked();
        body.interestBuildings = new ArrayList<>(interest);
        // 방해 금지를 끄면 같은 시간을 넣어 '구간 없음'으로 만든다 (서버는 null 을 '안 바꿈'으로 본다)
        body.quietStart = swQuiet.isChecked() ? quietStart : "00:00";
        body.quietEnd = swQuiet.isChecked() ? quietEnd : "00:00";
        ApiClient.match(this).saveSettings(body).enqueue(new ApiCallback<MatchModels.Settings>(this) {
            @Override public void ok(MatchModels.Settings s) { /* 저장됨 */ }

            @Override public void fail(String message) {
                Toast.makeText(NotiSettingActivity.this, "저장하지 못했어요: " + message, Toast.LENGTH_SHORT).show();
            }
        });
    }
}
