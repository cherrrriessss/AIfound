package com.aifound.app.ui;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.text.Html;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

import com.aifound.app.R;
import com.aifound.app.net.ApiClient;
import com.aifound.app.net.Models;
import com.aifound.app.util.Fmt;

/**
 * S17 분실 신고 완료 (이민서). 와이어프레임 S17_LostDone.
 * POST /lost 응답(LostOut)을 그대로 받아서 내 신고 요약 + '이미 등록된 습득물 중 비슷한 물건 n건'.
 */
public class LostDoneActivity extends AppCompatActivity {

    private static final String EXTRA_JSON = "lost_json";

    public static void open(Activity from, Models.LostOut l) {
        from.startActivity(new Intent(from, LostDoneActivity.class)
                .putExtra(EXTRA_JSON, ApiClient.gson().toJson(l)));
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_lost_done);
        Models.LostOut l = ApiClient.gson().fromJson(getIntent().getStringExtra(EXTRA_JSON), Models.LostOut.class);
        if (l == null) {
            finish();
            return;
        }

        ((TextView) findViewById(R.id.tvReportTitle)).setText(title(l));
        ((TextView) findViewById(R.id.tvReportSub)).setText(
                Fmt.join(l.buildings, ", ") + " · " + Fmt.lostRange(l.lostFrom, l.lostTo));

        int count = l.match != null ? l.match.count : 0;
        TextView info = findViewById(R.id.tvMatchInfo);
        if (l.match == null) {
            info.setText("매칭 서버에 연결하지 못했어요. 잠시 뒤 '분실물 매칭' 탭에서 다시 확인해 주세요.");
        } else if (count > 0) {
            info.setText(Html.fromHtml("이미 등록된 습득물 중 <b>비슷한 물건 " + count + "건</b>을 찾았어요",
                    Html.FROM_HTML_MODE_COMPACT));
        } else {
            info.setText("아직 비슷한 습득물이 없어요. 새로 등록되면 바로 알려드릴게요.");
        }

        findViewById(R.id.btnCandidates).setOnClickListener(v -> {
            MatchListActivity.open(this, l.id);
            finish();
        });
        findViewById(R.id.btnHome).setOnClickListener(v -> {
            Intent i = new Intent(this, HomeActivity.class);
            i.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
            startActivity(i);
            finish();
        });
    }

    /** '검정 Apple 에어팟 프로' / '검정 Apple 이어폰' */
    static String title(Models.LostOut l) {
        String color = Fmt.attr(l.attrs, "color");
        String brand = Fmt.attr(l.attrs, "brand");
        String model = Fmt.attr(l.attrs, "model");
        StringBuilder sb = new StringBuilder();
        if (color != null) sb.append(color).append(' ');
        if (brand != null) sb.append(brand).append(' ');
        sb.append(model != null ? model : l.category);
        return sb.toString().trim();
    }
}
